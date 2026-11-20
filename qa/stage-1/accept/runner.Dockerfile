FROM python:3.12-slim
COPY requirements.txt /requirements.txt
RUN python -m pip download --dest /wheels -r /requirements.txt exceptiongroup tomli
