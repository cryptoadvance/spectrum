FROM python:3.9.12-buster

RUN pip install --upgrade pip

WORKDIR /usr/src/app
ENV PYTHONUNBUFFERED 1
EXPOSE 8081

COPY . .
RUN mkdir /home/.ssh

RUN pip3 install -r requirements.txt && pip3 install -e .
CMD [ "python3", "-m", "cryptoadvance.spectrum", "server", "--config", "cryptoadvance.spectrum.config.ProductionConfig", "--host", "0.0.0.0"]