# 🧾 AI-Assisted Financial Data Assurance Framework  

## 📘 Overview  
This project proposes an **AI-assisted financial data assurance framework** designed to enhance confidence in financial information by combining **rule-based validation** with **machine learning–driven anomaly detection**.  

The system automatically checks financial data integrity, detects inconsistencies, and generates a **Trust Score** indicating the reliability of each financial record.  

---

## 🏗️ System Architecture  

The system architecture follows a modular, scalable design with five main layers:

### 1️⃣ **Data Ingestion Layer**
- Connects with multiple data sources such as ERP exports, ledgers, and Excel/CSV uploads.  
- Handles extraction, schema mapping, and normalization.

### 2️⃣ **Preprocessing Layer**
- Cleans and transforms input data.  
- Handles missing values, encodes categories, and computes derived metrics (e.g., ratios, z-scores).

### 3️⃣ **Validation Engine**
- Performs configurable rule-based checks:  
  - Balance validation  
  - Dependency verification  
  - Logical consistency between grouped ledgers  
- Flags potential data quality issues before ML analysis.

### 4️⃣ **Machine Learning Assurance Engine**
- Detects hidden anomalies and irregularities missed by rules.  
- Employs unsupervised models such as:
  - **Isolation Forest** — for numeric anomaly detection  
  - **Autoencoder (optional)** — for nonlinear feature relationships

### 5️⃣ **Trust Scoring & Visualization Layer**
- Combines rule violations and anomaly probabilities to compute a **Trust Score (0–100)**.  
- Visualizes results in an interactive **dashboard (Streamlit / Next.js)**.  
- Supports reviewer feedback for continuous model improvement.

---

## ⚙️ Workflow Summary  

1. **Data Ingestion**  
   Upload or connect ledgers, ERP exports, or statements.

2. **Preprocessing**  
   Normalize, clean, and encode financial data.

3. **Validation**  
   Apply predefined accounting and logical rules.

4. **Anomaly Detection (AI Layer)**  
   Identify subtle inconsistencies using ML models.

5. **Trust Scoring**  
   Compute reliability indices combining both validation and AI insights.

6. **Visualization & Feedback**  
   Present results on an interactive dashboard with reviewer feedback support.

---

## 🧩 Architecture Diagram  
<img width="1810" height="971" alt="Screenshot 2025-11-07 102528" src="https://github.com/user-attachments/assets/e4cf1578-f781-4ac3-b501-8ff88c45daba" />

