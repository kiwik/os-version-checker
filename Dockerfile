FROM python:3.8-buster

WORKDIR /opt/app

COPY ./ ./

RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir /opt/app/images_versions && \
    chmod 777 /opt && \
    chmod 777 /opt/app/images_versions

ENTRYPOINT [ "python3", "./VersionStatus.py"]
CMD [  "-r", "wallaby/22.03-LTS-SP2,train/22.03-LTS-SP2,yoga/22.09" ]
