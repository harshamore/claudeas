import streamlit as st
import pandas as pd
import numpy as np
from openai import OpenAI
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
from pathlib import Path
from io import BytesIO  # Added missing import

# Rest of the imports and logging setup remain the same...

class AS21Processor:
    def _init_(self):
        self.client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    # Previous methods remain the same...

    def _add_subsidiary_amounts(self, consolidated: pd.DataFrame, 
                              subsidiary: pd.DataFrame, 
                              eliminations: Dict,
                              ownership: float) -> pd.DataFrame:
        """Add subsidiary amounts to consolidated statements"""
        
        # Create a copy to avoid modifying the original
        result = consolidated.copy()
        
        # Convert ownership to float if it isn't already
        ownership_ratio = float(ownership) / 100.0
        minority_interest = 1.0 - ownership_ratio
        
        # Add subsidiary amounts line by line
        for column in subsidiary.columns:
            if column in result.columns:
                # Skip if it's an elimination account
                if 'intercompany' in column.lower():
                    continue
                
                # Ensure we're only operating on numeric columns
                if pd.api.types.is_numeric_dtype(subsidiary[column]):
                    # Convert to numeric if not already
                    subsidiary[column] = pd.to_numeric(subsidiary[column], errors='coerce')
                    result[column] = pd.to_numeric(result[column], errors='coerce')
                    
                    # Add subsidiary amount
                    result[column] = result[column].fillna(0) + (subsidiary[column].fillna(0) * ownership_ratio)
                    
                    # Add minority interest column if needed
                    mi_column = f"minority_interest_{column}"
                    result[mi_column] = subsidiary[column].fillna(0) * minority_interest
        
        return result

    def process_consolidation(self, parent_df: pd.DataFrame, 
                            subsidiary_dfs: List[pd.DataFrame]) -> pd.DataFrame:
        """Process consolidation according to AS21 rules"""
        
        # Initialize consolidated dataframe with parent data
        consolidated = parent_df.copy()
        
        # Process each subsidiary
        for sub_df in subsidiary_dfs:
            # Check ownership percentage (assuming column exists)
            # Default to 100 if ownership_percentage column doesn't exist
            ownership = float(sub_df.get('ownership_percentage', 100))
            
            if ownership > 50:  # AS21 control criterion
                # Perform eliminations
                eliminations = self._calculate_eliminations(consolidated, sub_df)
                
                # Add subsidiary amounts
                consolidated = self._add_subsidiary_amounts(consolidated, sub_df, 
                                                         eliminations, ownership)
        
        return consolidated

class ReportGenerator:
    # ReportGenerator class implementation remains the same...
    def generate_excel_report(self, consolidated_data: Dict, 
                            analysis_results: List[Dict]) -> bytes:
        """Generate formatted Excel report"""
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Write consolidated data as DataFrame
            if isinstance(consolidated_data, dict):
                consolidated_df = pd.DataFrame(consolidated_data)
            else:
                consolidated_df = consolidated_data
            
            consolidated_df.to_excel(writer, sheet_name='Consolidated', index=False)
            
            # Write analysis results
            analysis_df = pd.DataFrame([
                {'Sheet': result['sheet_name'], 'Analysis': result['analysis']}
                for result in analysis_results
            ])
            analysis_df.to_excel(writer, sheet_name='Analysis', index=False)
        
        return output.getvalue()

def main():
    # Main function implementation remains the same...
    pass

if _name_ == "_main_":
    main()
