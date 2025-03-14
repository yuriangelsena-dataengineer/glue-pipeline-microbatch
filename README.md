# AWS Glue ETL Pipeline: Integración S3 → RDS MySQL

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![AWS Glue](https://img.shields.io/badge/AWS-Glue-orange)](https://aws.amazon.com/glue/)
[![PySpark](https://img.shields.io/badge/PySpark-3.3-red)](https://spark.apache.org/docs/latest/api/python/)

**Transforma datos en movimiento** con este pipeline de procesamiento micro-batch que carga datos desde Amazon S3 a una base de datos relacional (RDS MySQL), implementando mejores prácticas de ingeniería de datos en AWS.

## 🚀 ¿Qué hace este proyecto?

Este repositorio contiene una solución completa para:
- **Ingesta de datos**: Archivos CSV/JSON desde S3
- **Transformaciones en tiempo real**: 
  - Normalización de precios
  - Auditoría de datos (timestamps)
  - Limpieza de valores nulos
- **Carga eficiente**: A una instancia RDS MySQL
- **Monitoreo**: Estadísticas operacionales en tiempo de ejecución

**Casos de uso ideales**:
- Reporting financiero
- Migración de data legacy
- Alimentación de dashboards en tiempo cuasi-real

## 🔑 Características Clave

| Tecnología           | Beneficio                                  |
|----------------------|--------------------------------------------|
| **AWS Glue 4.0**     | Procesamiento serverless sin infraestructura |
| **PySpark 3.3**      | Transformaciones distribuidas y escalables |
| **RDS MySQL**        | Almacenamiento transaccional seguro        |
| **VPC Networking**   | Comunicación segura entre servicios AWS    |

## ⚙️ Primeros Pasos

```bash
# 1. Clonar repositorio
git clone https://github.com/yuriangelsena-dataengineer
glue-pipeline-microbatch

# 2. Configurar entorno AWS
aws configure --profile glue-pipeline


## Arquitectura de la Solución
```mermaid
graph TD
    A[S3 Bucket] -->|Procesa datos| B(AWS Glue)
    B -->|Escribe resultados| C(RDS MySQL)
    B -->|Almacena logs| D[CloudWatch]
    E[JDBC Driver] -.->|Referencia| B
    F[IAM Role] -->|Permisos| B
    G[VPC] -->|Conectividad| C

Requisitos Previos
Recursos AWS:
Bucket S3 (pragma-data-pipeline)
RDS MySQL con credenciales habilitadas
VPC con acceso público o NAT Gateway
Locales:
MySQL Connector/J 8.0.28
Cuenta con permisos de administración en AWS

Configuración Paso a Paso
1. Configuración IAM para AWS Glue
Políticas requeridas:

{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:Get*",
                "s3:List*",
                "s3:Put*"
            ],
            "Resource": "arn:aws:s3:::pragma-data-pipeline/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "rds-db:connect"
            ],
            "Resource": "arn:aws:rds:us-east-1:1234567890:db:mysql-db"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
Crear Rol (CLI): aws iam create-role --role-name glue-s3-RDS-Role --assume-role-policy-document '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "glue.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}'

2. Configuración de Redes
Security Group (Entrada):
Type: MySQL/Aurora
Protocol: TCP
Port Range: 3306
Source: IP de Glue (o SG del VPC)

3. Subir JDBC Driver a S3
# Desde el repositorio clonado
git clone https://github.com/tu-usuario/pragma-data-pipeline.git
cd pragma-data-pipeline/jars

# Subir connector a S3
aws s3 cp mysql-connector-java-8.0.28.jar s3://pragma-data-pipeline/jars/

4. Crear Conexión JDBC en Glue
Parámetros de conexión:
Nombre: mysql-rds-connection
Tipo: JDBC
URL: jdbc:mysql://<endpoint-rds>:3306/<database>
Usuario: admin
Contraseña: *********
VPC: vpc-123456
Subredes: subnet-7890, subnet-4567
Grupo de seguridad: sg-0123

aws glue create-connection --connection-input '{
  "Name": "mysql-rds-connection",
  "ConnectionType": "JDBC",
  "PhysicalConnectionRequirements": {
    "SubnetId": "subnet-7890",
    "SecurityGroupIdList": ["sg-0123"],
    "AvailabilityZone": "us-east-1a"
  },
  "ConnectionProperties": {
    "JDBC_CONNECTION_URL": "jdbc:mysql://rds-endpoint:3306/mydb",
    "USERNAME": "admin",
    "PASSWORD": "mypassword"
  }
}'

Nombre: db-micro.batches-pragma
Tipo: Spark
IAM Role: GlueRDS-S3-Access
Librerías adicionales: s3://pragma-data-pipeline/jars/mysql-connector-java-8.0.28.jar
CLI Command:

Variables del Job:
--JOB_NAME = s3-to-rds-microbatch
--S3_BUCKET = s3://pragma-data-pipeline/raw-data/
--MYSQL_URL = jdbc:mysql://rds-endpoint:3306/mydb
--MYSQL_USER = admin
--MYSQL_PASSWORD = mypassword
--FILES_TO_PROCESS = file1.csv,file2.csv

6. Script de Transformación (glue_etl.py)
from awsglue.context import GlueContext
from pyspark.sql.functions import *

# Configuración inicial
glueContext = GlueContext(SparkContext.getOrCreate())

# Leer datos de S3
dynamic_frame = glueContext.create_dynamic_frame.from_options(
    "s3",
    {'paths': [S3_BUCKET]},
    format="csv",
    format_options={"withHeader": True}
)

# Convertir a DataFrame Spark
df = dynamic_frame.toDF()

# Transformaciones principales
processed_df = df.withColumn(
    "processed_timestamp", 
    current_timestamp()
).withColumn(
    "normalized_price", 
    col("price").cast("decimal(10,2)")
)

# Escribir en RDS MySQL
processed_df.write.format("jdbc") \
    .option("url", MYSQL_URL) \
    .option("dbtable", "transactions") \
    .option("user", MYSQL_USER) \
    .option("password", MYSQL_PASSWORD) \
    .mode("append") \
    .save()

Solución de Problemas Comunes
Error de Conexión a RDS:

Verificar Security Groups

Validar credenciales con:
aws s3 ls s3://pragma-data-pipeline/ --recursive
mysql -h <rds-endpoint> -u admin -p
aws logs filter-log-events --log-group-name /aws-glue/jobs/error
