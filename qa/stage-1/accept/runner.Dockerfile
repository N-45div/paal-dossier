FROM python:3.12-slim
RUN python -m pip download --dest /wheels 'pytest>=8,<10' 'httpx>=0.27,<1' exceptiongroup tomli
