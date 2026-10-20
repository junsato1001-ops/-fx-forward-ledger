"""Ledger and data-file column orders (Impl Part 3 §6, Part 4 §2.5, §8). Standard library only."""

FEATURE_FIELDS = [
    "Origin", "T_info_UTC",
    "F_US", "F_US_Status", "F_US_Reason", "F_US_Subreason", "F_US_Date", "F_US_Lag_Date", "F_US_Raw", "F_US_Raw_Lag",
    "F_US_Expected_Date", "F_US_Stale_Days",
    "F_JP", "F_JP_Status", "F_JP_Reason", "F_JP_Subreason", "F_JP_Date", "F_JP_Lag_Date", "F_JP_Raw", "F_JP_Raw_Lag",
    "F_JP_Expected_Date", "F_JP_Stale_Days",
    "F_POS", "F_POS_Status", "F_POS_Reason", "F_POS_Subreason", "F_POS_Report_Date", "F_POS_Usable_From_UTC",
    "F_POS_Expected_Release_UTC", "F_POS_Long", "F_POS_Short", "F_POS_Total_OI",
    "F_POS_Snapshot_Retrieved_At_UTC", "F_POS_Snapshot_SHA256",
    "Treasury_Retrieved_At_UTC", "Treasury_Bytes", "Treasury_SHA256", "Treasury_Private_Path",
    "MOF_Retrieved_At_UTC", "MOF_Bytes", "MOF_SHA256", "MOF_Path",
    "CFTC_Retrieved_At_UTC", "CFTC_Bytes", "CFTC_SHA256", "CFTC_Path",
    "Calendar_Anomalies", "Code_SHA256", "Run_ID"]
FORECAST_FIELDS = ["Model", "Pair", "Origin", "Horizon", "Cutoff_JST", "Last_Available_Fix", "Target_Start", "Target_End",
                   "Point_LogReturn", "P_Down", "P_Neutral", "P_Up", "PI10", "PI90", "Pool_N", "Mean_Z", "Q10_Z", "Q90_Z",
                   "Decision_Class", "Reason_Code", "Issued_At_UTC", "Code_SHA256", "Run_ID", "Parent", "Parent_Run_ID",
                   "Sigma_M0", "Parameter_State", "Beta_US", "Beta_JP", "Beta_POS", "Mu", "Feature_Row_Origin",
                   "Estimation_Row_Key"]
ESTIMATION_FIELDS = ["Origin", "Horizon", "Parameter_State", "N_Warmup", "N_Groups", "N_Gap_Origins",
                     "N_Excluded_Zero_Scale", "E_Input_SHA256", "Beta_US", "Beta_JP", "Beta_POS", "Solver_Status",
                     "Solver_Subreason", "Stage1_Iterations", "Stage2_Iterations", "UB_minus_LB", "Phi_beta2_minus_LB",
                     "J_Star", "Code_SHA256", "Run_ID"]
FETCH_FIELDS = ["Run_ID", "Source", "Source_URL", "Retrieved_At_UTC", "Byte_Count", "SHA256", "Path", "Normal",
                "Subreason", "Dates_Path"]
TREASURY_FIELDS = ["Retrieved_At_UTC", "Source_URL", "Byte_Count", "SHA256", "Private_Repository", "Private_Path",
                   "Private_Commit"]
