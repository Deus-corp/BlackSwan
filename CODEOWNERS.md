# CODEOWNERS — ответственные за код и документацию

# Этот файл определяет, кто автоматически запрашивается
# в качестве ревьюера при изменениях в указанных областях.

# --- Глобальные владельцы ---
# В случае отсутствия специфичных правил назначаются:
* @BlackSwanCoreTeam

# --- Манифест и неизменяемое ядро ---
/00_Manifesto/ @BlackSwanCoreTeam

# --- Ключевая архитектура ---
/01_Core_Architecture/ @BlackSwanCoreTeam

# --- ADR-записи ---
/ADR/ @BlackSwanCoreTeam

# --- Безопасность и стелс ---
/03_Domains/Cybersecurity_and_Stealth/ @BlackSwanCoreTeam

# --- Формальная верификация ---
/Appendices/Appendix_D_TLA_Specifications.md @BlackSwanCoreTeam
/Appendices/Appendix_I_Formal_Verification_Z3.md @BlackSwanCoreTeam
/Appendices/Appendix_Y_Verification_Report.md @BlackSwanCoreTeam

# --- Глобальная политика ---
/config/global_policy.json @BlackSwanCoreTeam