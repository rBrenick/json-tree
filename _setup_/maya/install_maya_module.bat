
:: json_tree is determined by the current folder name
for %%I in (.) do set json_tree=%%~nxI
SET CLEAN_json_tree=%json_tree:-=_%

:: Check if modules folder exists
if not exist %UserProfile%\Documents\maya\modules mkdir %UserProfile%\Documents\maya\modules

:: Delete .mod file if it already exists
if exist %UserProfile%\Documents\maya\modules\%json_tree%.mod del %UserProfile%\Documents\maya\modules\%json_tree%.mod

:: Create file with contents in users maya/modules folder
(echo|set /p=+ %json_tree% 1.0 %CD%\_setup_\maya & echo; & echo icons: ..\%CLEAN_json_tree%\icons)>%UserProfile%\Documents\maya\modules\%json_tree%.mod

:: end print
echo .mod file created at %UserProfile%\Documents\maya\modules\%json_tree%.mod



