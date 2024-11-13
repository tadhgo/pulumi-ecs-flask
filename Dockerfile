FROM python:3.12-alpine

WORKDIR /app

COPY app/requirements.txt . 
RUN pip install -r requirements.txt

COPY app/server.py .

EXPOSE 80

CMD ["python", "server.py"]