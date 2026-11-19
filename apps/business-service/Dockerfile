FROM maven:3.9.11-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
COPY src/main ./src/main
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/target/business-service-0.1.0.jar ./service.jar
USER 10001:10001
ENTRYPOINT ["java", "-jar", "/app/service.jar"]
