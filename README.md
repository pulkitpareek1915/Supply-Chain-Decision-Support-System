📦 Supply Chain Network Optimization & Multi-Warehouse Inventory Balancer
A Python-based Supply Chain Decision Support System that optimizes inventory movement across multiple warehouses using Linear Programming and provides an interactive analytics dashboard for inventory planning and operational decision-making.

Built for modern e-commerce supply chains such as Flipkart, Amazon, Walmart, and Meesho.

🚀 Features
Multi-Warehouse Inventory Optimization
Safety Stock Calculation
Reorder Point Computation
Transportation Problem Optimization using Linear Programming
Cost Optimization (Transfer vs External Replenishment)
Inventory Imbalance Detection
Interactive Streamlit Dashboard
Network Cost Analysis
Sensitivity Analysis
Operational KPI Dashboard
Warehouse Utilization Analysis
CSV Export of Recommended Transfers
📈 Problem Statement
Large e-commerce companies operate multiple fulfillment centers.

Some warehouses experience surplus inventory while others face stock shortages.

Instead of immediately placing expensive supplier orders, inventory can often be transferred between warehouses at a lower cost.

This project automatically determines:

Which warehouses should transfer inventory
How much inventory should be transferred
Whether external replenishment is more economical
Expected cost savings across the network
🏗️ System Architecture
Raw Warehouse Data │ ▼ Inventory Planning • Safety Stock • Reorder Point • Inventory Position │ ▼ Warehouse Classification • Surplus • Balanced • Deficit │ ▼ Transportation Optimization (Linear Programming) │ ▼ Transfer Recommendations │ ▼ KPI Dashboard & Cost Analytics

⚙️ Methodology
Stage 1 – Inventory Planning
For every Warehouse–SKU pair:

Safety Stock
Reorder Point
Inventory Imbalance
Stage 2 – Network Optimization
The optimizer solves a transportation problem using Linear Programming.

Objective:

Minimize

Transfer Cost
External Replenishment Cost
Subject to

Supply Constraints
Demand Constraints
Maximum Transfer Limits
Stage 3 – Operational KPIs
The system computes

Inventory Turnover
Fill Rate
Days of Inventory
Order Fulfillment Rate
Stockout Percentage
OTIF (Estimated)
Warehouse Utilization
📊 Dashboard Features
Interactive editing of

Warehouses
SKUs
Inventory
Demand
Lead Time
Transportation Distances
Visualization

Network Cost Comparison
Inventory Position
Surplus/Deficit Charts
Transfer Recommendations
Sensitivity Analysis
KPI Dashboard
🛠 Tech Stack
Python

Streamlit

Pandas

NumPy

SciPy (Linear Programming)

Plotly

📂 Project Structure
.
├── app.py                 # Streamlit Dashboard
├── balancer.py            # Optimization Engine
├── run_example.py         # Example Simulation
├── requirements.txt
└── README.md
▶️ Installation
Clone the repository

git clone <repo-url>

cd Supply-Chain-Network-Optimization
Create virtual environment

python -m venv venv
Activate

Windows

venv\Scripts\activate
Linux / macOS

source venv/bin/activate
Install dependencies

pip install -r requirements.txt
Run

streamlit run app.py
📈 Example Use Cases
Multi-Fulfillment Center Inventory Planning
Warehouse Balancing
Inventory Redistribution
Logistics Cost Reduction
Supply Chain Analytics
Inventory Optimization
Decision Support for Warehouse Managers
🎯 Key Outcomes
✔ Reduced Network Logistics Cost

✔ Improved Inventory Visibility

✔ Optimized Warehouse Balancing

✔ Reduced External Procurement

✔ Improved Operational Decision Making

✔ Interactive Supply Chain Analytics Dashboard

🔮 Future Enhancements
Demand Forecasting using Machine Learning
Vehicle Routing Optimization
Supplier Performance Analytics
Real-time Database Integration
Role-Based Dashboard
Live API Integration
AI-powered Root Cause Analysis# Supply-Chain-Decision-Support-System
