import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

# No role restriction - accessible to all
st.set_page_config(page_title="GL Analytics Dashboard", layout="wide")

st.title("📊 GL Reconciliation Analytics Dashboard")
st.markdown("### Comprehensive Analysis of GL Accounts")

# Load the Augmented GL data
@st.cache_data
def load_data():
    try:
        csv_path = Path("Augmented_GL_Reconciliation_Data.csv")
        df = pd.read_csv(csv_path)
        
        # Ensure numeric columns
        df['current_amount'] = pd.to_numeric(df['current_amount'], errors='coerce').fillna(0)
        df['prev_amount'] = pd.to_numeric(df['prev_amount'], errors='coerce').fillna(0)
        df['variance_value'] = pd.to_numeric(df['variance_value'], errors='coerce').fillna(0)
        df['timeline_deviation_days'] = pd.to_numeric(df['timeline_deviation_days'], errors='coerce').fillna(0)
        
        return df
    except FileNotFoundError:
        st.error("Augmented GL data file not found. Please ensure 'Augmented_GL_Reconciliation_Data.csv' exists.")
        return None

df = load_data()

if df is None:
    st.stop()

# Sidebar filters
st.sidebar.header("🔍 Filters")

# Department filter
all_departments = ["All"] + sorted(df['responsible_department'].dropna().unique().tolist())
selected_dept = st.sidebar.selectbox("Department", all_departments)

# Status filter
all_status = ["All"] + sorted(df['flag_green___red'].dropna().unique().tolist())
selected_status = st.sidebar.selectbox("Status", all_status)

# Timeline filter
timeline_options = ["All", "On Time", "Delayed"]
selected_timeline = st.sidebar.selectbox("Timeline Status", timeline_options)

# Apply filters
filtered_df = df.copy()
if selected_dept != "All":
    filtered_df = filtered_df[filtered_df['responsible_department'] == selected_dept]
if selected_status != "All":
    filtered_df = filtered_df[filtered_df['flag_green___red'] == selected_status]
if selected_timeline != "All":
    filtered_df = filtered_df[filtered_df['timeline_status'] == selected_timeline]

# ================== SUMMARY METRICS ==================
st.write("---")
st.subheader("📈 Key Metrics Summary")

# Classify working status
def classify_working_status(text):
    if pd.isna(text) or str(text).strip() == "":
        return "Pending"
    t = str(text).lower()
    if any(k in t for k in ["no balance", "not applicable", "there shall not be any balances", "nil balance"]):
        return "No Work Required"
    if any(k in t for k in ["support", "pending", "required", "working required", "reclassification entries"]):
        return "Pending"
    return "Complete"

filtered_df['working_status'] = filtered_df['working_needed'].apply(classify_working_status)

# Hygiene status
filtered_df['flag_norm'] = filtered_df['flag_green___red'].astype(str).str.strip().str.lower().fillna("unknown")
reviewed_count = len(filtered_df[filtered_df['flag_norm'].str.contains("green", na=False)])
pending_review_count = len(filtered_df[filtered_df['flag_norm'].str.contains("red", na=False)])
delayed_count = len(filtered_df[filtered_df['timeline_status'] == "Delayed"])

# Major variances (>2× mean)
mean_var = filtered_df['variance_value'].abs().mean()
threshold = mean_var * 2
major_var_count = len(filtered_df[filtered_df['variance_value'].abs() > threshold])

# Display metrics
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total GL Accounts", len(filtered_df))
    
with col2:
    pending_work = len(filtered_df[filtered_df['working_status'] == "Pending"])
    st.metric("Pending Workings", pending_work)
    
with col3:
    st.metric("Reviewed (Green)", reviewed_count)
    
with col4:
    st.metric("Timeline Delays", delayed_count)
    
with col5:
    st.metric("Major Variances", major_var_count)

# ================== DETAILED SUMMARY TABLE ==================
st.write("---")
st.subheader("📋 Detailed Summary")

summary_data = {
    "Metric": [
        "Total GL Accounts",
        "Pending Backup / Supporting Workings",
        "Complete Workings",
        "No Work Required (Nil/NA)",
        "Reviewed GLs (Green)",
        "Pending Reviews (Red)",
        "Timeline Deviations (Delayed)",
        f"Major GL Variances (>2× Mean = {threshold:.2f}%)"
    ],
    "Count": [
        len(filtered_df),
        len(filtered_df[filtered_df['working_status'] == "Pending"]),
        len(filtered_df[filtered_df['working_status'] == "Complete"]),
        len(filtered_df[filtered_df['working_status'] == "No Work Required"]),
        reviewed_count,
        pending_review_count,
        delayed_count,
        major_var_count
    ]
}

summary_df = pd.DataFrame(summary_data)
st.dataframe(summary_df, use_container_width=True, hide_index=True)

# ================== VISUALIZATIONS ==================
st.write("---")
st.subheader("📊 Visual Analytics")

# Create tabs for different analysis views
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview", 
    "🔍 Hygiene Analysis", 
    "⏰ Timeline Analysis", 
    "📈 Variance Analysis",
    "🏢 Department Analysis"
])

with tab1:
    st.write("### Summary Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Summary bar chart
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(summary_df["Metric"], summary_df["Count"], color="skyblue", edgecolor="black")
        ax.set_xticklabels(summary_df["Metric"], rotation=45, ha="right")
        ax.set_title("GL Reconciliation Summary")
        ax.set_ylabel("Count")
        plt.tight_layout()
        st.pyplot(fig)
    
    with col2:
        # Working status distribution
        work_counts = filtered_df["working_status"].value_counts()
        fig, ax = plt.subplots(figsize=(8, 8))
        colors = ['#ff9999', '#66b3ff', '#99ff99']
        ax.pie(work_counts.values, labels=work_counts.index, autopct="%1.1f%%", 
               startangle=120, colors=colors)
        ax.set_title("Working / Supporting File Status")
        st.pyplot(fig)

with tab2:
    st.write("### GL Hygiene - Reviewed vs Pending")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Hygiene pie chart
        flag_counts = pd.Series({
            "Reviewed (Green)": reviewed_count,
            "Pending Review (Red)": pending_review_count,
            "Unknown": len(filtered_df) - reviewed_count - pending_review_count
        })
        
        fig, ax = plt.subplots(figsize=(8, 8))
        colors = ['lightgreen', 'salmon', 'lightgrey']
        ax.pie(flag_counts.values, labels=flag_counts.index, autopct="%1.1f%%", 
               startangle=120, colors=colors)
        ax.set_title("GL Hygiene Status")
        st.pyplot(fig)
    
    with col2:
        # Status by department
        if 'responsible_department' in filtered_df.columns:
            status_dept = filtered_df.groupby(['responsible_department', 'flag_green___red']).size().unstack(fill_value=0)
            if not status_dept.empty:
                fig, ax = plt.subplots(figsize=(10, 6))
                status_dept.plot(kind='barh', stacked=True, ax=ax, color=['lightgreen', 'salmon'])
                ax.set_title("Status Distribution by Department")
                ax.set_xlabel("Count")
                ax.legend(title="Status", bbox_to_anchor=(1.05, 1))
                plt.tight_layout()
                st.pyplot(fig)

with tab3:
    st.write("### Timeline Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Timeline status pie
        timeline_counts = filtered_df['timeline_status'].value_counts()
        fig, ax = plt.subplots(figsize=(8, 8))
        colors = ['#90EE90', '#FFB6C6']
        ax.pie(timeline_counts.values, labels=timeline_counts.index, autopct="%1.1f%%",
               startangle=120, colors=colors)
        ax.set_title("Timeline Performance")
        st.pyplot(fig)
    
    with col2:
        # Average delay by department
        if 'responsible_department' in filtered_df.columns:
            avg_delay = (filtered_df.groupby('responsible_department')['timeline_deviation_days']
                        .mean().sort_values(ascending=False).head(10))
            
            if not avg_delay.empty:
                fig, ax = plt.subplots(figsize=(10, 6))
                avg_delay.plot(kind='barh', color='purple', edgecolor='black', ax=ax)
                ax.invert_yaxis()
                ax.set_title("Average Timeline Deviation by Department (Top 10)")
                ax.set_xlabel("Days")
                plt.tight_layout()
                st.pyplot(fig)
    
    # Timeline deviation distribution
    st.write("#### Timeline Deviation Distribution")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.hist(filtered_df['timeline_deviation_days'], bins=30, color='lightblue', edgecolor='black')
    ax.axvline(0, color='green', linestyle='--', label='On Time', linewidth=2)
    ax.set_title("Distribution of Timeline Deviations")
    ax.set_xlabel("Deviation (Days)")
    ax.set_ylabel("Frequency")
    ax.legend()
    plt.tight_layout()
    st.pyplot(fig)

with tab4:
    st.write("### Variance Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Variance distribution
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(filtered_df['variance_value'], bins=40, color='lightblue', edgecolor='black')
        ax.axvline(threshold, color='red', linestyle='--', 
                  label=f'±{threshold:.2f}% Threshold (2× Mean)', linewidth=2)
        ax.axvline(-threshold, color='red', linestyle='--', linewidth=2)
        ax.axvline(0, color='green', linestyle='-', label='Zero Variance', linewidth=1)
        ax.set_title("Distribution of GL Variance (%)")
        ax.set_xlabel("% Variance")
        ax.set_ylabel("Frequency")
        ax.legend()
        plt.tight_layout()
        st.pyplot(fig)
    
    with col2:
        # Top variances
        top_variances = filtered_df.nlargest(10, 'variance_value', keep='all')[
            ['g_l_account_number', 'variance_value', 'current_amount', 'prev_amount']
        ].copy()
        
        st.write("#### Top 10 Positive Variances")
        st.dataframe(top_variances, use_container_width=True, hide_index=True)
    
    # Variance by amount range
    st.write("#### Variance vs Amount Analysis")
    fig, ax = plt.subplots(figsize=(12, 6))
    scatter = ax.scatter(filtered_df['prev_amount'], filtered_df['variance_value'], 
                        c=filtered_df['variance_value'].abs(), cmap='RdYlGn_r', 
                        alpha=0.6, edgecolor='black')
    ax.axhline(threshold, color='red', linestyle='--', alpha=0.5)
    ax.axhline(-threshold, color='red', linestyle='--', alpha=0.5)
    ax.axhline(0, color='green', linestyle='-', alpha=0.3)
    ax.set_title("Variance % vs Previous Amount")
    ax.set_xlabel("Previous Amount (₹)")
    ax.set_ylabel("Variance %")
    plt.colorbar(scatter, ax=ax, label='Absolute Variance %')
    plt.tight_layout()
    st.pyplot(fig)

with tab5:
    st.write("### Department Analysis")
    
    if 'responsible_department' in filtered_df.columns:
        # Pending workings by department
        st.write("#### Pending Workings by Department")
        pend_dept = (filtered_df[filtered_df['working_status'] == "Pending"]
                    .groupby('responsible_department').size()
                    .sort_values(ascending=False).head(15))
        
        if not pend_dept.empty:
            fig, ax = plt.subplots(figsize=(12, 6))
            pend_dept.plot(kind='barh', color='orange', edgecolor='black', ax=ax)
            ax.invert_yaxis()
            ax.set_title("Pending Workings by Department (Top 15)")
            ax.set_xlabel("Count")
            plt.tight_layout()
            st.pyplot(fig)
        
        # Department summary table
        st.write("#### Department-wise Summary")
        dept_summary = filtered_df.groupby('responsible_department').agg({
            'g_l_account_number': 'count',
            'variance_value': lambda x: x.abs().mean(),
            'timeline_deviation_days': 'mean'
        }).round(2)
        dept_summary.columns = ['GL Count', 'Avg Abs Variance %', 'Avg Timeline Deviation (Days)']
        dept_summary = dept_summary.sort_values('GL Count', ascending=False)
        st.dataframe(dept_summary, use_container_width=True)
        
        # Criticality analysis
        st.write("#### Criticality Distribution by Department")
        if 'c_m_l' in filtered_df.columns:
            crit_dept = filtered_df.groupby(['responsible_department', 'c_m_l']).size().unstack(fill_value=0)
            if not crit_dept.empty:
                fig, ax = plt.subplots(figsize=(12, 6))
                crit_dept.plot(kind='barh', stacked=True, ax=ax)
                ax.set_title("GL Criticality by Department")
                ax.set_xlabel("Count")
                ax.legend(title="Criticality", bbox_to_anchor=(1.05, 1))
                plt.tight_layout()
                st.pyplot(fig)

# ================== DETAILED DATA TABLE ==================
st.write("---")
st.subheader("📄 Detailed GL Data")

# Select columns to display
display_columns = [
    'g_l_account_number', 'main_head', 'sub_head', 'responsible_department',
    'current_amount', 'prev_amount', 'variance_value', 
    'flag_green___red', 'timeline_status', 'timeline_deviation_days',
    'working_status'
]

# Filter to available columns
display_columns = [col for col in display_columns if col in filtered_df.columns]

display_df = filtered_df[display_columns].copy()

# Format numeric columns
if 'current_amount' in display_df.columns:
    display_df['current_amount'] = display_df['current_amount'].apply(lambda x: f"₹{x:,.2f}")
if 'prev_amount' in display_df.columns:
    display_df['prev_amount'] = display_df['prev_amount'].apply(lambda x: f"₹{x:,.2f}")
if 'variance_value' in display_df.columns:
    display_df['variance_value'] = display_df['variance_value'].apply(lambda x: f"{x:.2f}%")

st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)

# ================== EXPORT OPTIONS ==================
st.write("---")
st.subheader("📥 Export Data")

col1, col2 = st.columns(2)

with col1:
    # Export filtered data
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="Download Filtered Data (CSV)",
        data=csv,
        file_name=f"filtered_gl_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

with col2:
    # Export summary
    summary_csv = summary_df.to_csv(index=False)
    st.download_button(
        label="Download Summary (CSV)",
        data=summary_csv,
        file_name=f"gl_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

# ================== FOOTER ==================
st.write("---")
st.caption(f"Dashboard generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total Records: {len(filtered_df)}")
