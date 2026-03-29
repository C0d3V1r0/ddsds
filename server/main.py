# Точка входа FastAPI-приложения Nullius
import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import Depends, FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from config import load_config
from deployment import background_tasks_enabled, get_deployment_state, init_deployment_role, release_primary_lock
from db import init_db, start_writer, stop_writer
from api import health, metrics, services, processes, logs, security, integrations, self_protection, deployment
from api import ml_status
from api import risk
from api.auth import require_auth, set_api_token
from integrations.service import init_integrations_runtime, start_integrations_loops, stop_integrations_loops
from ws.agent import agent_ws_handler, init_security
from ws.frontend import frontend_ws_handler
from security.mode import init_operation_mode
from security.detector import Detector

SECRET_TOKEN_BYTES = 32

_writer_task = None
_bg_tasks: list = []


def get_config_path() -> str:
    """Возвращает путь к YAML-конфигу с учётом env-переопределения."""
    return os.environ.get("NULLIUS_CONFIG", "nullius.yaml")


def get_db_path() -> str:
    """Возвращает путь к SQLite БД с учётом env-переопределения."""
    return os.environ.get("NULLIUS_DB", "data/nullius.db")


def create_app(
    config_path: str = "nullius.yaml",
    db_path: str = "data/nullius.db",
) -> FastAPI:
    """Создаёт и настраивает FastAPI-приложение."""
    config = load_config(config_path)
    deployment_state = init_deployment_role(
        str(config.deployment.role),
        str(config.deployment.node_name),
        str(config.deployment.primary_lock_path),
    )

    detector = Detector(config.security)
    init_security(detector, config.security, config.ml)
    init_integrations_runtime(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        from tasks.retention import cleanup_old_data
        from tasks.expiry import expire_blocked_ips
        from ml.trainer import init_models, train_anomaly_from_db, _set_anomaly_status
        from api.risk import capture_risk_snapshot

        global _writer_task, _bg_tasks
        await init_db(db_path)
        health.set_db_status(True)
        _writer_task = await start_writer(db_path)
        await init_operation_mode(str(config.security.operation_mode))
        app.state.deployment = get_deployment_state()

        # Загрузка ML-моделей с диска или обучение classifier
        try:
            await init_models(db_path)
        except Exception:
            logging.getLogger("nullius").warning("Ошибка инициализации ML-моделей", exc_info=True)

        # Проверка истёкших блокировок IP каждые 60 сек
        async def _expiry_loop():
            while True:
                try:
                    await expire_blocked_ips(db_path)
                except Exception:
                    logging.getLogger("nullius").warning("Ошибка в expiry loop", exc_info=True)
                await asyncio.sleep(60)

        # Очистка старых данных каждый час
        async def _retention_loop():
            while True:
                await asyncio.sleep(3600)
                try:
                    await cleanup_old_data(db_path)
                except Exception:
                    logging.getLogger("nullius").warning("Ошибка в retention loop", exc_info=True)

        async def _risk_snapshot_loop():
            snapshot_interval = max(60, int(config.risk.snapshot_interval))
            try:
                await capture_risk_snapshot(app)
            except Exception:
                logging.getLogger("nullius").warning("Ошибка первого risk snapshot", exc_info=True)
            while True:
                await asyncio.sleep(snapshot_interval)
                try:
                    await capture_risk_snapshot(app)
                except Exception:
                    logging.getLogger("nullius").warning("Ошибка в risk snapshot loop", exc_info=True)

        # Обучение anomaly detector: первый прогон не откладываем слишком надолго,
        # а дальнейший интервал берём из конфига, чтобы runtime был предсказуемым.
        async def _ml_training_loop():
            training_period = max(300, int(config.ml.training_period))
            initial_delay = min(900, training_period)
            _set_anomaly_status("pending", "waiting_for_first_run", next_run_at=int(time.time()) + initial_delay)
            await asyncio.sleep(initial_delay)
            while True:
                try:
                    await train_anomaly_from_db(
                        db_path,
                        hours=max(1, int(config.ml.baseline_hours)),
                        min_samples=max(50, int(config.ml.min_clean_samples)),
                        max_clean_events=max(1, int(config.ml.max_clean_events)),
                        base_buffer_seconds=max(30, int(config.ml.baseline_buffer_seconds)),
                        host_profile=str(config.ml.host_profile).strip() or "generic",
                        maintenance_window_seconds=max(60, int(config.ml.maintenance_window_seconds)),
                        maintenance_commands=tuple(config.ml.maintenance_commands),
                    )
                except Exception:
                    _set_anomaly_status("failed", "training_failed", next_run_at=int(time.time()) + training_period)
                    logging.getLogger("nullius").warning("Ошибка в ML training loop", exc_info=True)
                else:
                    from ml.trainer import get_anomaly_status

                    current = get_anomaly_status()
                    _set_anomaly_status(
                        str(current["status"]),
                        str(current["reason_code"]),
                        samples_count=int(current["samples_count"]),
                        filtered_samples_count=int(current["filtered_samples_count"]),
                        discarded_samples_count=int(current["discarded_samples_count"]),
                        required_samples=int(current["required_samples"]),
                        event_count=int(current["event_count"]),
                        max_event_count=int(current["max_event_count"]),
                        maintenance_event_count=int(current["maintenance_event_count"]),
                        host_profile=str(current["host_profile"]),
                        filter_window_seconds=int(current["filter_window_seconds"]),
                        maintenance_window_seconds=int(current["maintenance_window_seconds"]),
                        dataset_quality_score=int(current["dataset_quality_score"]),
                        dataset_quality_label=str(current["dataset_quality_label"]),
                        dataset_noise_label=str(current["dataset_noise_label"]),
                        weighted_event_pressure=int(current["weighted_event_pressure"]),
                        excluded_windows_count=int(current["excluded_windows_count"]),
                        next_run_at=int(time.time()) + training_period,
                    )
                await asyncio.sleep(training_period)

        if background_tasks_enabled():
            _bg_tasks = [
                asyncio.create_task(_expiry_loop()),
                asyncio.create_task(_retention_loop()),
                asyncio.create_task(_risk_snapshot_loop()),
                asyncio.create_task(_ml_training_loop()),
                *start_integrations_loops(),
            ]
        else:
            logging.getLogger("nullius").warning(
                "Nullius запущен в standby-режиме: mutating background loops и активная реакция отключены"
            )
            _bg_tasks = []
        yield
        for task in _bg_tasks:
            task.cancel()
        # Дожидаемся завершения отменённых задач перед остановкой writer
        await asyncio.gather(*_bg_tasks, return_exceptions=True)
        await stop_integrations_loops()
        if _writer_task:
            await stop_writer(_writer_task)
        release_primary_lock()

    # Секрет агента: приоритет env > файл agent.key > генерация временного
    agent_secret = os.environ.get("NULLIUS_AGENT_SECRET", "")
    if not agent_secret:
        # install.sh кладёт ключ рядом с конфигом: /opt/nullius/config/agent.key
        key_path = Path(config_path).with_name("agent.key")
        if key_path.exists():
            agent_secret = key_path.read_text().strip()
    if not agent_secret:
        agent_secret = secrets.token_hex(SECRET_TOKEN_BYTES)
        logging.getLogger("nullius").warning(
            "NULLIUS_AGENT_SECRET не задан, сгенерирован временный. "
            "Задайте через env или config/agent.key для продакшна!"
        )

    # Bearer auth для REST API — отдельный токен, не агентский секрет
    api_token = ""
    if config.api.require_bearer_auth:
        api_token = os.environ.get("NULLIUS_API_TOKEN", "").strip() or config.api.token.strip()
        if not api_token:
            raise RuntimeError(
                "Bearer auth включён, но api.token / NULLIUS_API_TOKEN не задан. "
                "Для безопасности API token не должен fallback'иться к agent secret."
            )
    set_api_token(api_token)

    # UI WebSocket token тоже отделяем от agent secret.
    # При желании можно переиспользовать API token, но только как UI-секрет,
    # а не как доверенный секрет агента.
    ui_ws_token = ""
    if config.api.require_ws_token:
        ui_ws_token = (
            os.environ.get("NULLIUS_WS_TOKEN", "").strip()
            or config.api.ws_token.strip()
            or api_token
        )
        if not ui_ws_token:
            raise RuntimeError(
                "WS auth включён, но api.ws_token / NULLIUS_WS_TOKEN не задан. "
                "Допустимо также переиспользовать UI API token, если включён Bearer auth."
            )

    app = FastAPI(title="Nullius API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.state.config = config
    app.state.config_path = config_path
    app.state.db_path = db_path
    app.state.deployment = deployment_state
    # Health — публичный, остальные роутеры защищены Bearer-токеном
    app.include_router(health.router)
    app.include_router(metrics.router, dependencies=[Depends(require_auth)])
    app.include_router(services.router, dependencies=[Depends(require_auth)])
    app.include_router(processes.router, dependencies=[Depends(require_auth)])
    app.include_router(logs.router, dependencies=[Depends(require_auth)])
    app.include_router(security.router, dependencies=[Depends(require_auth)])
    app.include_router(integrations.router, dependencies=[Depends(require_auth)])
    app.include_router(ml_status.router, dependencies=[Depends(require_auth)])
    app.include_router(risk.router, dependencies=[Depends(require_auth)])
    app.include_router(self_protection.router, dependencies=[Depends(require_auth)])
    app.include_router(deployment.router, dependencies=[Depends(require_auth)])

    @app.websocket("/ws/agent")
    async def ws_agent(ws: WebSocket):
        await agent_ws_handler(ws, agent_secret)

    @app.websocket("/ws/live")
    async def ws_live(ws: WebSocket):
        await frontend_ws_handler(ws, ui_ws_token)

    return app


def app_factory() -> FastAPI:
    """Синхронная фабрика для uvicorn --factory."""
    return create_app(
        config_path=get_config_path(),
        db_path=get_db_path(),
    )


if __name__ == "__main__":
    import uvicorn

    async def run() -> None:
        app = create_app(
            config_path=get_config_path(),
            db_path=get_db_path(),
        )
        uvi_config = uvicorn.Config(app, host="127.0.0.1", port=8000)
        server = uvicorn.Server(uvi_config)
        await server.serve()

    asyncio.run(run())
