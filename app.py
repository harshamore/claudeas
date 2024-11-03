import streamlit as st
import pandas as pd
import openai
from fpdf import FPDF
import tempfile
import os

# Initialize OpenAI API key
openai.api_key = "YOUR_OPENAI_API_KEY"

def consolidate_accounts(df_parent, df_subsidiary):
    # Ensure both dataframes have the same columns before proceeding
    common_columns = df_parent.columns.intersection(df_subsidiary.columns)
    df_parent = df_parent[common_columns]
    df_subsidiary = df_subsidiary[common_columns]

    # Filter only numeric columns for summing
    numeric_columns = df_parent.select_dtypes(include="number").columns
    df_parent = df_parent[numeric_columns]
    df_subsidiary = df_subsidiary[numeric_columns]

    # Placeholder checks for guidance requests
    if "inter_company_balance" in df_subsidiary.columns:
        clarification = consult_openai_for_as21_clarity("guidance on inter-company balances in AS 21")
        st.write("AS 21 Guidance (Inter-company Balances):", clarification)
    
    if "goodwill" not in df_subsidiary.columns:
        clarification = consult_openai_for_as21_clarity("goodwill calculation guidance under AS 21")
        st.write("AS 21 Guidance (Goodwill Calculation):", clarification)

    # Perform consolidation
    df_consolidated = pd.concat([df_parent, df_subsidiary]).groupby(level=0).sum()
    return df_consolidated

def consult_openai_for_as21_clarity(query):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in Indian Accounting Standard AS 21."},
                {"role": "user", "content": f"Provide guidance on AS 21 for: {query}"}
            ],
            max_tokens=100
        )
        return response.choices[0].message['content'].strip()
    except Exception:
        st.error("Error with OpenAI API: Unable to retrieve guidance.")
        return "Unable to retrieve AS 21 guidance at this time."

def convert_excel_to_pdf(df, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Consolidated Financial Statements: {filename}", ln=True, align="C")
    
    for i, row in df.iterrows():
        row_text = ', '.join(f"{str(cell)}" for cell in row)
        pdf.cell(200, 10, txt=row_text, ln=True)

    pdf_output = f"{filename}.pdf"
    pdf.output(pdf_output)
    return pdf_output

def main():
    st.title("Financial Accounts Consolidation App (AS 21 Compliant)")

    uploaded_files = st.file_uploader("Upload Excel files for consolidation", accept_multiple_files=True, type=["xlsx"])

    if uploaded_files:
        company_data = {}
        for file in uploaded_files:
            df = pd.read_excel(file, sheet_name=0)
            company_data[file.name] = df

        parent_company = st.selectbox("Select the Parent Company", list(company_data.keys()))
        if parent_company:
            df_parent = company_data[parent_company]

            subsidiary_files = [name for name in company_data if name != parent_company]
            if subsidiary_files:
                consolidated_dfs = []
                for sub_name in subsidiary_files:
                    st.write(f"Processing subsidiary: {sub_name}")
                    df_sub = company_data[sub_name]
                    try:
                        consolidated_df = consolidate_accounts(df_parent, df_sub)
                        consolidated_dfs.append(consolidated_df)
                    except Exception as e:
                        st.error(f"Error consolidating {sub_name} with {parent_company}: {e}")
                        continue

                if consolidated_dfs:
                    final_consolidated_df = pd.concat(consolidated_dfs).drop_duplicates()
                    
                    # Generate PDF of the consolidated data
                    pdf_file_path = convert_excel_to_pdf(final_consolidated_df, "Consolidated_Report")
                    with open(pdf_file_path, "rb") as pdf_file:
                        st.download_button(
                            label="Download Consolidated Report as PDF",
                            data=pdf_file,
                            file_name="Consolidated_Report.pdf",
                            mime="application/pdf"
                        )

                    # Export to Excel as well
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
                        final_consolidated_df.to_excel(tmp_excel.name, index=False)
                        tmp_excel.seek(0)
                        st.download_button(
                            label="Download Consolidated Report as Excel",
                            data=tmp_excel,
                            file_name="Consolidated_Report.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

if __name__ == "__main__":
    main()
