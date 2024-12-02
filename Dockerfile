FROM python:3.9-slim
WORKDIR /app
COPY ebookServer.py /app
RUN pip install flask werkzeug PyMuPDF pillow ebooklib watchdog
EXPOSE 8085
CMD ["python", "ebookServer.py"]
