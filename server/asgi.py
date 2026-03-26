import asyncio

from main import create_app, get_config_path, get_db_path


app = asyncio.run(
    create_app(
        config_path=get_config_path(),
        db_path=get_db_path(),
    )
)
