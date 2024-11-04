import streamlit as st
import pandas as pd
from io import BytesIO

st.title("Financial Accounts Consolidation using IND AS 21")

st.header("Upload Excel Files")

# Upload parent company Excel file
parent_file = st.file_uploader("Upload Parent Company Excel File", type=['xlsx'], key='parent')

# Upload subsidiary companies' Excel files
subsidiary_files = st.file_uploader(
    "Upload Subsidiary Company Excel Files",
    type=['xlsx'],
    accept_multiple_files=True,
    key='subsidiaries'
)

# Collect ownership percentages for each subsidiary
subsidiary_info = {}
if subsidiary_files:
    st.header("Enter Ownership Percentages for Subsidiaries")
    for file in subsidiary_files:
        sub_name = file.name
        ownership = st.number_input(
            f"Ownership percentage of {sub_name} (%)",
            min_value=0.0,
            max_value=100.0,
            value=100.0,
            key=sub_name
        )
        subsidiary_info[sub_name] = {'file': file, 'ownership': ownership}

if parent_file is not None and subsidiary_files:
    st.header("Processing and Consolidating Data...")

    # Read parent company Excel file
    parent_excel = pd.ExcelFile(parent_file)
    parent_data = {}
    for sheet_name in parent_excel.sheet_names:
        df = parent_excel.parse(sheet_name)
        parent_data[sheet_name] = df

    # Read subsidiary companies' Excel files
    subsidiaries_data = {}
    for sub_name, info in subsidiary_info.items():
        file = info['file']
        excel = pd.ExcelFile(file)
        sub_data = {}
        for sheet_name in excel.sheet_names:
            df = excel.parse(sheet_name)
            sub_data[sheet_name] = df
        subsidiaries_data[sub_name] = {'data': sub_data, 'ownership': info['ownership']}

    # Consolidate data according to IND AS 21
    consolidated_data = {}
    for sheet_name in parent_excel.sheet_names:
        parent_df = parent_data.get(sheet_name)
        consolidated_df = parent_df.copy()

        for sub_name, sub_info in subsidiaries_data.items():
            sub_df = sub_info['data'].get(sheet_name)
            ownership = sub_info['ownership'] / 100.0  # Convert to decimal

            # Adjust subsidiary data for ownership percentage
            sub_df_adjusted = sub_df.copy()
            numeric_cols = sub_df_adjusted.select_dtypes(include='number').columns
            sub_df_adjusted[numeric_cols] = sub_df_adjusted[numeric_cols] * ownership

            # Append adjusted subsidiary data
            consolidated_df = pd.concat([consolidated_df, sub_df_adjusted])

        # Sum up the data
        consolidated_df = consolidated_df.groupby(consolidated_df.columns[0]).sum().reset_index()

        # Eliminate inter-company transactions
        intercompany_accounts = consolidated_df[
            consolidated_df[consolidated_df.columns[0]].str.contains('Intercompany', case=False, na=False)
        ]
        if not intercompany_accounts.empty:
            consolidated_df = consolidated_df[
                ~consolidated_df[consolidated_df.columns[0]].str.contains('Intercompany', case=False, na=False)
            ]

        consolidated_data[sheet_name] = consolidated_df

    # Prepare consolidated Excel file for download
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')

    for sheet_name, df in consolidated_data.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    writer.save()
    processed_data = output.getvalue()

    st.success("Consolidation Completed")
    st.download_button(
        label="Download Consolidated Excel File",
        data=processed_data,
        file_name="Consolidated_Financial_Statements.xlsx"
    )
else:
    st.info("Please upload both parent and subsidiary company Excel files.")
