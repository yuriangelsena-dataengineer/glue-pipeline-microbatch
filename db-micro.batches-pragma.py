import sys
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, count, to_timestamp, current_timestamp
from pyspark.sql.functions import min as spark_min, max as spark_max
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.types import DoubleType, IntegerType

# Configuración inicial
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

# Parámetros configurables
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'S3_BUCKET', 'MYSQL_URL', 
                          'MYSQL_USER', 'MYSQL_PASSWORD', 'FILES_TO_PROCESS'])
s3_bucket = args['S3_BUCKET']
mysql_url = args['MYSQL_URL']
mysql_user = args['MYSQL_USER']
mysql_password = args['MYSQL_PASSWORD']
files_to_process = args['FILES_TO_PROCESS'].split(',')

# Estadísticas en memoria
global_stats = {
    "total_rows": 0,
    "total_price": 0.0,
    "min_price": float('inf'),
    "max_price": float('-inf')
}

def write_stats_to_db(stats, table_name):
    """Escribe estadísticas en MySQL"""
    stats_df = spark.createDataFrame([(
        stats["total_rows"],
        stats["total_price"] / stats["total_rows"] if stats["total_rows"] > 0 else 0,
        stats["min_price"],
        stats["max_price"]
    )], ["total_rows", "avg_price", "min_price", "max_price"])
    
    stats_df.withColumn("execution_time", current_timestamp()) \
            .write.format("jdbc") \
            .option("url", mysql_url) \
            .option("dbtable", table_name) \
            .option("user", mysql_user) \
            .option("password", mysql_password) \
            .option("driver", "com.mysql.cj.jdbc.Driver") \
            .mode("append") \
            .save()

try:
    for file_name in files_to_process:
        print(f"\n🔹 Procesando: {file_name}")
        
        # 1. Leer y transformar datos
        df = spark.read.option("header", "true") \
                      .csv(f"{s3_bucket}/{file_name}") \
                      .withColumn("timestamp", to_timestamp(col("timestamp"), "M/d/yyyy")) \
                      .withColumn("price", col("price").cast(DoubleType())) \
                      .withColumn("user_id", col("user_id").cast(IntegerType())) \
                      .fillna({"price": 0.0})
        
        # 2. Escribir en MySQL
        df.select("timestamp", "price", "user_id") \
          .write.format("jdbc") \
          .option("url", mysql_url) \
          .option("dbtable", "transactions") \
          .option("user", mysql_user) \
          .option("password", mysql_password) \
          .option("driver", "com.mysql.cj.jdbc.Driver") \
          .mode("append") \
          .save()
        
        # 3. Calcular estadísticas del batch
        batch_stats = df.agg(
            count("*").alias("total_rows"),
            sum("price").alias("total_price"),
            spark_min("price").alias("min_price"),
            spark_max("price").alias("max_price")
        ).collect()[0]
        
        # 4. Actualizar estadísticas globales
        global_stats["total_rows"] += batch_stats["total_rows"] or 0
        global_stats["total_price"] += batch_stats["total_price"] or 0.0
        global_stats["min_price"] = min(global_stats["min_price"], batch_stats["min_price"] or float('inf'))
        global_stats["max_price"] = max(global_stats["max_price"], batch_stats["max_price"] or float('-inf'))
        
        # 5. Registrar estadísticas
        write_stats_to_db(global_stats, "stats")
        
        print(f"""
        ✅ Estadísticas actualizadas:
           - Total filas: {global_stats['total_rows']}
           - Precio mínimo: {global_stats['min_price']}
           - Precio máximo: {global_stats['max_price']}
           - Precio promedio: {global_stats['total_price'] / global_stats['total_rows'] if global_stats['total_rows'] > 0 else 0:.2f}
        """)

    job.commit()
    print("\n✅ Proceso completado")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    raise e