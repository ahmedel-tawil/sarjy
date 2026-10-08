import uvicorn

from sarjy_gateway.app import build_text_to_speech, create_app
from sarjy_gateway.logs import configure_logging
from sarjy_gateway.settings import Settings


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    # log_config=None stops uvicorn installing its own handlers, so its logs use our JSON
    # format. Cloud Run already logs every request, so uvicorn's access log is off.
    uvicorn.run(
        create_app(settings, build_text_to_speech(settings)),
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
