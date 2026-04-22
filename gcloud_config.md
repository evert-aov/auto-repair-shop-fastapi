# ⚙️ Configuración de Google Cloud CLI (gcloud) para Speech-to-Text en Linux

## 📌 Objetivo

Configurar el entorno local para autenticar y consumir la API de voz de Google Cloud sin usar claves JSON, utilizando credenciales seguras (ADC).

---

# 🧱 1. Instalación de Google Cloud CLI

## 🔹 Instalar `gcloud`

```bash
curl https://sdk.cloud.google.com | bash
```

## 🔹 Aplicar cambios en la terminal

```bash
exec -l $SHELL
```

## 🔹 Verificar instalación

```bash
gcloud --version
```

---

# 🔐 2. Autenticación de usuario

## 🔹 Login básico (cuenta Google)

```bash
gcloud auth login
```

📌 Abre el navegador y autentica tu cuenta.

---

## 🔹 Login para aplicaciones (ADC)

```bash
gcloud auth application-default login
```

📌 Este paso es CRÍTICO:

* Permite que tu código (FastAPI, Python, etc.) acceda a las APIs
* Reemplaza completamente el uso de archivos JSON

---

# 🧭 3. Seleccionar proyecto

```bash
gcloud config set project <TU_PROJECT_ID>
gcloud auth application-default set-quota-project <TU_PROJECT_ID>
```

📌 Usa el mismo proyecto donde trabajarás con:

* Google Speech-to-Text

---

# ⚙️ 4. Activar la API

```bash
gcloud services enable storage.googleapis.com
gcloud services enable speech.googleapis.com
gcloud services enable aiplatform.googleapis.com
```

📌 Asegura que la API esté habilitada en el proyecto.

---

# convertir audio a formato compatible (flac)

```terminal
sudo pacman -S ffmpeg
```


