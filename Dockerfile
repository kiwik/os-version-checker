FROM python:3.8-buster

WORKDIR /opt/app

COPY ./ ./

RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir /opt/app/images_versions && \
    chmod 777 /opt && \
    chmod 777 /opt/app/images_versions

ENTRYPOINT [ "python3", "./VersionStatus.py"]
CMD [ "-t", "html", "-r", "stein,train,ussuri", "-n", "index.html" ]
