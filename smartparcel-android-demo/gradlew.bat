@ECHO OFF
SETLOCAL
SET APP_HOME=%~dp0
IF DEFINED JAVA_HOME GOTO useJavaHome
SET JAVA_EXE=java.exe
GOTO execute
:useJavaHome
SET JAVA_EXE=%JAVA_HOME%\bin\java.exe
:execute
"%JAVA_EXE%" %JAVA_OPTS% %GRADLE_OPTS% -classpath "%APP_HOME%gradle\wrapper\gradle-wrapper-standard.jar" org.gradle.wrapper.GradleWrapperMain %*
SET EXIT_CODE=%ERRORLEVEL%
ENDLOCAL & EXIT /B %EXIT_CODE%
