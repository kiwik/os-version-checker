FROM python:3.8-buster

WORKDIR /opt/app

COPY ./ ./

RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT [ "python3", "./VersionStatus.py"]
CMD [ "-t", "html", "-r", "rocky,stein,train,ussuri", "-f", "index.html" ]
