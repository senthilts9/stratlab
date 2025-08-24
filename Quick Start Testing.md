# 🐳 Local Docker Environment Testing Guide

## Quick Start Testing

### 1. **Start the Environment**
```bash
# Clone and start StratLab
git clone https://github.com/senthilts9/stratlab.git
cd stratlab
docker compose up --build
```

### 2. **Verify Services Are Running**
```bash
# Check all containers are up
docker compose ps

# Expected output:
# stratlab-streamlit-1     Up      0.0.0.0:8501->8501/tcp
# stratlab-celery-1        Up      
# stratlab-redis-1         Up      6379/tcp
# stratlab-dask-scheduler-1 Up     8786/tcp, 8787/tcp
# stratlab-dask-worker-1   Up      
```

### 3. **Access the Application**
🌐 **Main Interface:** http://localhost:8501

### 4. **Test the Complete Workflow**

#### **Step 1: Upload Test Data**
- Navigate to **Upload** page
- Download sample CSV: [SP500 Sample Data](sample-data/sp500_sample.csv)
- Drag & drop or browse to upload

#### **Step 2: Validate Data**
- Go to **Factor Model** page  
- Click **🔍 Test Data Loading**
- Verify success message and data structure

#### **Step 3: Run Analysis**
- Set shrinkage λ parameter (default: 0.1)
- Click **Run Analysis**
- Monitor task dispatch confirmation

#### **Step 4: View Results**
- Navigate to **Results** page
- Verify **Task status: SUCCESS**
- Check interactive charts and summary table

## 🔧 Troubleshooting Commands

### **Service Health Checks**
```bash
# Check Streamlit logs
docker compose logs streamlit --tail=20

# Check Celery worker status  
docker compose logs celery --tail=20

# Check Redis connectivity
docker compose exec redis redis-cli ping
# Should return: PONG

# Test Celery task registration
docker compose exec celery celery -A backend.tasks inspect registered
```

### **Performance Monitoring**
```bash
# Monitor resource usage
docker stats

# Check container network
docker compose exec streamlit ping redis
docker compose exec celery ping redis
```

### **Data Validation**
```bash
# Verify shared volume
docker compose exec streamlit ls -la /shared/uploads/

# Check file permissions
docker compose exec celery ls -la /shared/uploads/
```

## 📊 Sample Test Data

Create a test CSV file (`test_data.csv`):
```csv
Date,Symbol,Px
2024-01-01,AAPL,185.00
2024-01-02,AAPL,187.50
2024-01-03,AAPL,184.25
2024-01-01,MSFT,420.00
2024-01-02,MSFT,425.30
2024-01-03,MSFT,418.75
2024-01-01,SPY,485.00
2024-01-02,SPY,488.20
2024-01-03,SPY,482.90
```

## 🎯 Expected Test Results

### **Data Validation Output:**
```
✅ Data loaded successfully!
Shape: [6, 4]
Columns: ['Date', 'Symbol', 'Px', 'Ret']
Data Types: {
  "Date": "datetime64",
  "Symbol": "object", 
  "Px": "float64",
  "Ret": "float64"
}
```

### **Analysis Results:**
- **AAPL Beta:** ~0.8-1.2 (typical range)
- **MSFT Beta:** ~0.9-1.1 (typical range)  
- **VaR Values:** Small positive numbers (0.001-0.01 range)
- **Task Status:** SUCCESS

## 🚀 Advanced Testing

### **Load Testing**
```bash
# Generate larger test dataset
docker compose exec celery python -c "
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Generate 1000+ rows of test data
dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'SPY']
data = []

for date in dates:
    for symbol in symbols:
        price = 100 + np.random.randn() * 10
        data.append({'Date': date, 'Symbol': symbol, 'Px': price})

df = pd.DataFrame(data)
df.to_csv('/shared/uploads/large_test.csv', index=False)
print(f'Generated {len(df)} rows of test data')
"

# Test with large dataset
# Upload large_test.csv and run full analysis
```

### **Concurrent User Simulation**
```bash
# Test multiple analysis requests
for i in {1..3}; do
  curl -X POST http://localhost:8501/api/analyze &
done
wait
```

## 📋 Test Checklist

- [ ] All 5 Docker containers start successfully
- [ ] Streamlit UI loads at http://localhost:8501  
- [ ] File upload accepts CSV/Parquet files
- [ ] Data validation shows correct schema
- [ ] Celery processes tasks without errors
- [ ] Results display interactive charts
- [ ] VaR calculations produce reasonable values
- [ ] Beta coefficients are in expected ranges
- [ ] Task status updates in real-time
- [ ] System handles edge cases gracefully

## 🐛 Common Issues & Fixes

### **Port Already in Use**
```bash
# Kill process using port 8501
lsof -ti:8501 | xargs kill -9
# Or use different port
docker compose up -p 8502:8501
```

### **Container Memory Issues**
```bash
# Increase Docker memory to 4GB+
# Restart Docker Desktop
docker system prune -a
```

### **Task Stuck in PENDING**
```bash
# Restart Celery worker
docker compose restart celery
# Check Redis connection
docker compose logs redis
```

---

## 🌟 Success Indicators

When everything works correctly:
- ✅ **Upload**: File saves to `/shared/uploads/`
- ✅ **Validation**: Data schema displays correctly  
- ✅ **Processing**: Task status changes PENDING → RUNNING → SUCCESS
- ✅ **Results**: Charts render with real financial metrics
- ✅ **Performance**: Analysis completes in <30 seconds for typical datasets

**Test URL for verification:** http://localhost:8501

Your StratLab environment is production-ready when all tests pass! 🎉