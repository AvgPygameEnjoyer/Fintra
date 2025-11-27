# 1️⃣ Base Python image
FROM python:3.12-slim

# 2️⃣ Set working directory inside the container
WORKDIR /app

# 3️⃣ Copy only dependency file first to enable caching
COPY requirements.txt .

# 4️⃣ Upgrade pip and install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 5️⃣ Copy the rest of your code
COPY . .

# 6️⃣ Expose port (optional for Render, usually 10000+ auto assigned)
EXPOSE 10000

# 7️⃣ Start your app using Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--workers", "3"]
