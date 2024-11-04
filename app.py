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

    st.write("Parent Data:")
    for sheet_name, df in parent_data.items():
        st.write(f"Sheet: {sheet_name}, Shape: {df.shape}")
        st.write(df.head())

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

    st.write("Subsidiaries Data:")
    for sub_name, sub_info in subsidiaries_data.items():
        st.write(f"Subsidiary: {sub_name}")
        for sheet_name, df in sub_info['data'].items():
            st.write(f"Sheet: {sheet_name}, Shape: {df.shape}")
            st.write(df.head())

    # Consolidate data according to IND AS 21
    consolidated_data = {}
    for sheet_name in parent_excel.sheet_names:
        parent_df = parent_data.get(sheet_name)
        consolidated_df = parent_df.copy()

        for sub_name, sub_info in subsidiaries_data.items():
            sub_df = sub_info['data'].get(sheet_name)
            ownership = sub_info['ownership'] / 100.0  # Convert to decimal

            if sub_df is not None:
                # Ensure columns align
                sub_df_adjusted = sub_df.copy()
                # Align columns by reindexing
                sub_df_adjusted = sub_df_adjusted.reindex(columns=parent_df.columns)
                
                # Adjust subsidiary data for ownership percentage
                numeric_cols = sub_df_adjusted.select_dtypes(include='number').columns
                st.write(f"Before Ownership Adjustment for {sub_name}, Sheet: {sheet_name}")
                st.write(sub_df_adjusted[numeric_cols].head())

                sub_df_adjusted[numeric_cols] = sub_df_adjusted[numeric_cols] * ownership

                st.write(f"After Ownership Adjustment for {sub_name}, Sheet: {sheet_name}")
                st.write(sub_df_adjusted[numeric_cols].head())

                # Append adjusted subsidiary data
                consolidated_df = pd.concat([consolidated_df, sub_df_adjusted], ignore_index=True)
            else:
                st.warning(f"Sheet '{sheet_name}' not found in subsidiary '{sub_name}'. Skipping.")

        st.write("Consolidated DataFrame after concatenation:")
        st.write(consolidated_df.head())
        st.write(f"Consolidated DataFrame shape: {consolidated_df.shape}")

        # Specify the correct column name for grouping
        # Replace 'Account Code' with the actual column name you use as the key
        group_by_column = 'Account Code'  # Example: 'Account Code', 'Account Name', etc.

        if group_by_column not in consolidated_df.columns:
            st.error(f"Group by column '{group_by_column}' not found in DataFrame columns.")
            st.write("Available columns:", consolidated_df.columns.tolist())
            st.stop()  # Stop execution if the group_by_column is not found
        else:
            st.write(f"Using '{group_by_column}' as the grouping key.")

        # Select numeric columns to sum
        numeric_cols = consolidated_df.select_dtypes(include=['number']).columns.tolist()
        st.write("Numeric Columns:", numeric_cols)

        # Perform groupby sum on numeric columns without setting index
        consolidated_df = consolidated_df.groupby(group_by_column, as_index=False)[numeric_cols].sum()

        st.write("Consolidated DataFrame after groupby and sum:")
        st.write(consolidated_df.head())
        st.write(f"Consolidated DataFrame shape after groupby: {consolidated_df.shape}")

        # Handle non-numeric columns if they exist
        non_numeric_cols = [col for col in consolidated_df.columns if col not in numeric_cols + [group_by_column]]
        if non_numeric_cols:
            non_numeric_data = consolidated_df[[group_by_column] + non_numeric_cols].drop_duplicates(subset=group_by_column)
            consolidated_df = pd.merge(consolidated_df, non_numeric_data, on=group_by_column, how='left')

        # Eliminate inter-company transactions
        # Adjust the filter condition as per your data
        intercompany_filter = consolidated_df[group_by_column].astype(str).str.contains(
            'Intercompany|Inter-company|IC', case=False, na=False
        )
        rows_to_remove = intercompany_filter.sum()
        st.write(f"Number of inter-company transaction rows to remove: {rows_to_remove}")

        if intercompany_filter.any():
            consolidated_df = consolidated_df[~intercompany_filter]

        st.write(f"Data after removing inter-company transactions:")
        st.write(consolidated_df.head())
        st.write(f"Final DataFrame shape: {consolidated_df.shape}")

        if consolidated_df.empty:
            st.warning(f"The consolidated DataFrame for sheet '{sheet_name}' is empty after processing.")
        else:
            consolidated_data[sheet_name] = consolidated_df

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
        st.error("No data to consolidate after processing all sheets.")

else:
    st.info("Please upload both parent and subsidiary company Excel files.")
