import streamlit as st
import pandas as pd
import numpy as np
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

if parent_file is not None and subsidiary_files:
    st.header("Processing and Consolidating Data...")

    # Read parent company Excel file
    parent_excel = pd.ExcelFile(parent_file)
    parent_sheets = parent_excel.sheet_names
    parent_data = {}
    for sheet in parent_sheets:
        df = parent_excel.parse(sheet)
        parent_data[sheet] = df

    # Read subsidiary companies' Excel files
    subsidiaries_data = {}
    for file in subsidiary_files:
        sub_name = file.name
        st.write(f"Processing subsidiary: {sub_name}")
        sub_excel = pd.ExcelFile(file)
        sub_sheets = sub_excel.sheet_names
        sub_data = {}
        for sheet in sub_sheets:
            df = sub_excel.parse(sheet)
            sub_data[sheet] = df
        subsidiaries_data[sub_name] = sub_data

    # Collect ownership percentages for each subsidiary
    st.header("Enter Ownership Percentages for Subsidiaries")
    ownership_percentages = {}
    for file in subsidiary_files:
        sub_name = file.name
        ownership = st.number_input(
            f"Ownership percentage of {sub_name} (%)",
            min_value=0.0,
            max_value=100.0,
            value=100.0,
            key=f"ownership_{sub_name}"
        )
        ownership_percentages[sub_name] = ownership / 100.0  # Convert to decimal

    # Initialize consolidated data
    consolidated_data = {}

    # Get all sheets present in parent and subsidiaries
    all_sheets = set(parent_sheets)
    for sub_data in subsidiaries_data.values():
        all_sheets.update(sub_data.keys())

    for sheet in all_sheets:
        # Initialize an empty DataFrame for this sheet
        consolidated_df = pd.DataFrame()

        # Process parent data
        if sheet in parent_data:
            parent_df = parent_data[sheet]
            consolidated_df = parent_df.copy()

        # Process subsidiary data
        for sub_name, sub_data in subsidiaries_data.items():
            if sheet in sub_data:
                sub_df = sub_data[sheet].copy()

                # Align columns with parent_df
                sub_df = sub_df.reindex(columns=consolidated_df.columns, fill_value=0)

                # Adjust for ownership percentage
                numeric_cols = sub_df.select_dtypes(include=[np.number]).columns.tolist()
                sub_df[numeric_cols] = sub_df[numeric_cols] * ownership_percentages[sub_name]

                # Append to consolidated_df
                consolidated_df = pd.concat([consolidated_df, sub_df], ignore_index=True)

        if not consolidated_df.empty:
            # Identify key column(s) for grouping
            possible_keys = ['Account Code', 'Account Name', 'GL Code']
            key_cols = [col for col in possible_keys if col in consolidated_df.columns]
            if key_cols:
                group_by_cols = key_cols
            else:
                # Use all non-numeric columns as keys
                group_by_cols = consolidated_df.select_dtypes(exclude=[np.number]).columns.tolist()

            # Sum numeric data
            consolidated_df = consolidated_df.groupby(group_by_cols, as_index=False).sum()

            # Eliminate inter-company transactions
            intercompany_keywords = ['Intercompany', 'Inter-company', 'IC']
            pattern = '|'.join(intercompany_keywords)
            intercompany_filter = consolidated_df.apply(
                lambda row: row.astype(str).str.contains(pattern, case=False, na=False).any(), axis=1
            )
            consolidated_df = consolidated_df[~intercompany_filter]

            # Store the consolidated data for this sheet
            consolidated_data[sheet] = consolidated_df

    if consolidated_data:
        # Prepare consolidated Excel file for download
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for sheet_name, df in consolidated_data.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        processed_data = output.getvalue()

        st.success("Consolidation Completed")
        st.download_button(
            label="Download Consolidated Excel File",
            data=processed_data,
            file_name="Consolidated_Financial_Statements.xlsx"
        )
    else:
        st.error("No data to consolidate.")

else:
    st.info("Please upload both parent and subsidiary company Excel files.")
