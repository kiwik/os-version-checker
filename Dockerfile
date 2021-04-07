FROM python:3.8-buster

WORKDIR /opt/app

COPY ./ ./

RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir /opt/app/images_versions && \
    chmod 777 /opt && \
    chmod 777 /opt/app/images_versions

ENTRYPOINT [ "python3", "./VersionStatus.py"]
CMD [  "-r", "victoria-21.03,train-ussuri,train-20.03-LTS-SP1" ]
