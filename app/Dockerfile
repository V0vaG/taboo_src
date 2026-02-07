FROM python:3.9-slim

ARG VERSION
ENV VERSION=$VERSION

ARG B_NUM
ENV B_NUM=$B_NUM

ARG SERVER_PORT
ENV SERVER_PORT=$SERVER_PORT

WORKDIR /app

COPY ./requirements.txt /app/

RUN pip install -r requirements.txt

COPY . /app/

CMD gunicorn --timeout 120 -w 4 -b 0.0.0.0:5000 wsgi:app

