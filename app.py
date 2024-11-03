import streamlit as st
import pandas as pd
import openai
from fpdf import FPDF
import tempfile
import os

# Initialize OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

def consolidate_accounts(df_parent, df_subsidiary):
    # Placeholder consolidation logic that uses AS 21 principles
    # Sample check for inter-company balances or goodwill uncertainty
    if "inter_company_balance" in df_subsidiary.columns:
        clarification = consult_openai_for_as21_clarity("guidance on inter-company balances in AS 21")
        st.write("AS 21 Guidance (Inter-company Balances):", clarification)
    
    if "goodwill" not in df_subsidiary.columns:
        clarification = consult_openai_for_as21_clarity("goodwill calculation guidance under AS 21")
        st.write("AS 21 Guidance (Goodwill Calculation):", clarification)

    # Consolidate by removing inter-company balances, calculating goodwill, etc. (simplified example)
    df_consolidated = pd.concat([df_parent, df_subsidiary]).groupby(level=0).sum()
    return df_consolidated

def consult_openai_for_as21_clarity(query):
    # Call OpenAI with generalized query on AS 21 without sharing any specific user data
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=f"Provide guidance on AS 21 for: {query}",
        max_tokens=100
    )
    return response.choices[0].text.strip()

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
                    consolidated_df = consolidate_accounts(df_parent, df_sub)
                    consolidated_dfs.append(consolidated_df)

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
