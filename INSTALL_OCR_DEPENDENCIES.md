# Instalação de Dependências OCR

## 🔍 Problema
Se você está vendo o erro:
```
tesseract is not installed or it's not in your PATH
```

Isso significa que o Tesseract OCR não está instalado no sistema operacional.

## 🛠️ Soluções por Sistema Operacional

### Windows

1. **Opção 1: Instalador Oficial**
   - Baixe o instalador do [GitHub Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
   - Execute o instalador
   - Adicione ao PATH: `C:\Program Files\Tesseract-OCR`

2. **Opção 2: Chocolatey**
   ```cmd
   choco install tesseract
   ```

3. **Opção 3: Scoop**
   ```cmd
   scoop install tesseract
   ```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install tesseract-ocr
sudo apt install tesseract-ocr-por  # Para português
```

### Linux (CentOS/RHEL/Fedora)

```bash
sudo yum install tesseract
# ou
sudo dnf install tesseract
```

### macOS

```bash
brew install tesseract
brew install tesseract-lang  # Para idiomas adicionais
```

### Docker (Para deployment)

Adicione ao seu Dockerfile:

```dockerfile
# Para Ubuntu base
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Para Alpine base
RUN apk add --no-cache \
    tesseract-ocr \
    tesseract-ocr-data-por \
    poppler-utils
```

## 🐳 Docker Compose (Exemplo)

```yaml
version: '3.8'
services:
  backend:
    build: .
    environment:
      - OCR_ENABLED=true
    volumes:
      - ./uploads:/app/uploads
    depends_on:
      - db
  
  # Adicione dependências OCR no build
```

## 📋 Verificação da Instalação

Para verificar se está funcionando:

```python
import pytesseract
print(pytesseract.get_tesseract_version())
```

Ou use o endpoint de status do sistema:
```bash
curl http://localhost:5000/api/health/ocr-status
```

## 🔧 Configuração Avançada

### Configurar PATH manualmente (Windows)

1. Vá em Sistema → Configurações Avançadas
2. Variáveis de Ambiente
3. Adicione à variável PATH:
   ```
   C:\Program Files\Tesseract-OCR
   ```

### Configurar caminho customizado no código

```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

## 🚀 Deploy em Produção

### Netlify Functions

Para Netlify, adicione ao `netlify.toml`:

```toml
[build]
  command = "npm run build"
  
[build.environment]
  NODE_VERSION = "18"
  
[[plugins]]
  package = "netlify-plugin-playwright"
```

### Render/Railway

Adicione ao seu `requirements.txt`:
```
pytesseract==0.3.10
Pillow>=9.0.0
```

E configure o buildpack ou Dockerfile apropriado.

### Vercel

Para Vercel, use:
```json
{
  "functions": {
    "pages/api/*.py": {
      "runtime": "python3.9"
    }
  }
}
```

## 🏥 Modo Fallback

O sistema foi configurado para funcionar em **modo demonstração** quando OCR não está disponível:

- ✅ Sistema continua funcionando
- ✅ Usa dados de exemplo
- ✅ Permite testar o fluxo completo
- ⚠️ Dados extraídos são simulados

## 📞 Suporte

Se continuar com problemas:

1. Verifique os logs do sistema
2. Teste a instalação manualmente
3. Abra uma issue no repositório

---

**Status**: Sistema funciona sem OCR em modo demonstração ✅