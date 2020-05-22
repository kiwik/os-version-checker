FROM python:3.8-buster

WORKDIR /opt/app

COPY requirements.txt ./
COPY VersionStatus.py ./
COPY /templates ./templates

RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python3", "./VersionStatus.py", "-t", "html", "-r", "rocky,stein,train,ussuri", "-f", "index.html" ]
