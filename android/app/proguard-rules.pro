# JSch picks its ciphers, key exchanges and signatures by class name at run time
# (JSch.getConfig), so R8 can't see them used. Its Bouncy Castle glue (com.jcraft.jsch.bc)
# refers to the Bouncy Castle classes it needs directly, which keeps those too.
-keep class com.jcraft.jsch.** { *; }

# Optional JSch integrations the app doesn't ship.
-dontwarn com.sun.jna.**
-dontwarn org.apache.logging.log4j.**
-dontwarn org.slf4j.**
-dontwarn org.newsclub.net.unix.**
-dontwarn org.ietf.jgss.**
-dontwarn javax.naming.**
-dontwarn java.lang.invoke.StringConcatFactory
