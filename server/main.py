# - Точка входа FastAPI-приложения Nullius
import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import Depends, FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from config import load_config
from db import init_db, start_writer, stop_writer
from api import health, metrics, services, processes, logs, security
from api import ml_status
from api.auth import require_auth, set_api_token
from ws.agent import agent_ws_handler, init_security
from ws.frontend import frontend_ws_handler
from security.detector import Detector
from security.responder import Responder

# - Размер токена в байтах для генерации секрета
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

    # - Инициализация security detector + responder
    detector = Detector(config.security)
    responder = Responder(auto_block=config.security.auto_block)
    init_security(detector, responder, config.security)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        from tasks.retention import cleanup_old_data
        from tasks.expiry import expire_blocked_ips
        from ml.trainer import init_models, train_anomaly_from_db

        global _writer_task, _bg_tasks
        await init_db(db_path)
        health.set_db_status(True)
        _writer_task = await start_writer(db_path)

        # - Инициализация ML-моделей (загрузка с диска или обучение classifier)
        try:
            await init_models(db_path)
        except Exception:
            logging.getLogger("nullius").warning("# - Ошибка инициализации ML-моделей", exc_info=True)

        # - Фоновая задача: проверка истёкших блокировок IP каждые 60 сек
        async def _expiry_loop():
            while True:
                try:
                    await expire_blocked_ips(db_path)
                except Exception:
                    logging.getLogger("nullius").warning("# - Ошибка в expiry loop", exc_info=True)
                await asyncio.sleep(60)

        # - Фоновая задача: очистка старых данных каждый час
        async def _retention_loop():
            while True:
                await asyncio.sleep(3600)
                try:
                    await cleanup_old_data(db_path)
                except Exception:
                    logging.getLogger("nullius").warning("# - Ошибка в retention loop", exc_info=True)

        # - Фоновая задача: обучение anomaly detector (первичное через 24ч, потом каждые 7 дней)
        async def _ml_training_loop():
            # - Первая проверка через 1 час, потом каждые 6 часов
            await asyncio.sleep(3600)
            while True:
                try:
                    await train_anomaly_from_db(db_path, hours=24)
                except Exception:
                    logging.getLogger("nullius").warning("# - Ошибка в ML training loop", exc_info=True)
                await asyncio.sleep(6 * 3600)

        _bg_tasks = [
            asyncio.create_task(_expiry_loop()),
            asyncio.create_task(_retention_loop()),
            asyncio.create_task(_ml_training_loop()),
        ]
        yield
        for task in _bg_tasks:
            task.cancel()
        # - Ждём завершения отменённых задач перед остановкой writer
        await asyncio.gather(*_bg_tasks, return_exceptions=True)
        if _writer_task:
            await stop_writer(_writer_task)

    # - Секрет для аутентификации агента: приоритет env > файл > дефолт для разработки
    agent_secret = os.environ.get("NULLIUS_AGENT_SECRET", "")
    if not agent_secret:
        key_path = Path(config_path).parent / "config" / "agent.key"
        if key_path.exists():
            agent_secret = key_path.read_text().strip()
    if not agent_secret:
        # - В продакшне секрет обязателен, в dev генерируем временный
        agent_secret = secrets.token_hex(SECRET_TOKEN_BYTES)
        logging.getLogger("nullius").warning(
            "# - NULLIUS_AGENT_SECRET не задан, сгенерирован временный. "
            "Задайте через env или config/agent.key для продакшна!"
        )

    # - Bearer auth для UI/API включается только если это явно разрешено конфигом
    set_api_token(agent_secret if config.api.require_bearer_auth else "")

    app = FastAPI(title="Nullius API", lifespan=lifespan)

    # - CORS: ограничиваем источники запросов
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization"],
    )

    app.state.config = config
    app.state.db_path = db_path
    # - Health эндпоинт публичный, остальные защищены Bearer-токеном
    app.include_router(health.router)
    app.include_router(metrics.router, dependencies=[Depends(require_auth)])
    app.include_router(services.router, dependencies=[Depends(require_auth)])
    app.include_router(processes.router, dependencies=[Depends(require_auth)])
    app.include_router(logs.router, dependencies=[Depends(require_auth)])
    app.include_router(security.router, dependencies=[Depends(require_auth)])
    app.include_router(ml_status.router, dependencies=[Depends(require_auth)])

    @app.websocket("/ws/agent")
    async def ws_agent(ws: WebSocket):
        await agent_ws_handler(ws, agent_secret)

    @app.websocket("/ws/live")
    async def ws_live(ws: WebSocket):
        await frontend_ws_handler(ws, agent_secret if config.api.require_ws_token else "")

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
