# Spinoco Download Pipeline

🎤 **Complete audio processing pipeline** for downloading, transcribing, and anonymizing Spinoco call center recordings.

## 🎯 Purpose

Downloads call recordings from Spinoco API, transcribes them using Whisper, and anonymizes sensitive data for further processing.

## 🏗️ Architecture

**3-Step Pipeline:**
1. **Ingest** - Download recordings from Spinoco API
2. **Transcribe** - Convert audio to text using Whisper
3. **Anonymize** - Remove sensitive data and number transcripts

## 🚀 Features

- **Spinoco API Integration** - Direct download from production API
- **Whisper Large-v3** - Best available transcription quality
- **Czech language optimized** - Perfect for technical support
- **Idempotent processing** - Resume capability with SQLite state
- **Parallel processing** - Multiple files simultaneously
- **Data anonymization** - Phone numbers, emails, IBAN removal
- **Production ready** - Error handling and retry logic

## 📁 Directory Structure

```
spinoco-download/
├── src/                    # Core modules
│   ├── spinoco_client.py   # Spinoco API client
│   ├── transcriber.py      # Whisper transcription
│   └── main.py            # Main entry point
├── steps/                  # Pipeline steps
│   ├── ingest_spinoco/    # Step 1: Download recordings
│   ├── transcribe_asr_adapter/ # Step 2: Transcribe audio
│   └── anonymize/         # Step 3: Anonymize transcripts
├── common/                 # Shared libraries
│   ├── lib/               # Core utilities
│   └── schemas/           # Pydantic models
├── data/                  # Processing directories
│   ├── 01_recordings/     # Downloaded audio files
│   ├── 02_transcripts/    # Transcribed text files
│   └── metadata/          # Processing metadata
└── config/               # Configuration files
```

## 🔧 Installation

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install pyyaml
```

## 📝 Configuration

### Environment Variables (.env)
```env
# Spinoco API
SPINOCO_API_BASE=https://api.spinoco.com
SPINOCO_TOKEN=your_production_token
SPINOCO_PROTOCOL_VERSION=2

# Processing
TEST_MODE=false
MAX_PARALLEL=2
```

### Step Configuration
Each step has its own `config.yaml`:
- `steps/ingest_spinoco/input/config.yaml` - API settings
- `steps/transcribe_asr_adapter/input/config.yaml` - Whisper settings  
- `steps/anonymize/input/config.yaml` - Anonymization rules

## 🚀 Usage

### Complete Pipeline
```bash
# Step 1: Download 5 recordings
venv\Scripts\python.exe steps\ingest_spinoco\run.py --mode incr --limit 5 --config steps\ingest_spinoco\input\config.yaml

# Step 2: Transcribe downloaded recordings
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --config steps\transcribe_asr_adapter\input\config.yaml --input_run_id <RUN_ID>

# Step 3: Anonymize transcripts
venv\Scripts\python.exe steps\anonymize\run.py --config steps\anonymize\input\config.yaml --input_run_id <RUN_ID>
```

### Individual Steps
```bash
# Download more recordings
venv\Scripts\python.exe steps\ingest_spinoco\run.py --mode incr --limit 10 --config steps\ingest_spinoco\input\config.yaml

# Retry failed transcriptions
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --config steps\transcribe_asr_adapter\input\config.yaml --retry
```

## 📊 Output Format

### Downloaded Recordings
- **Location**: `steps/ingest_spinoco/output/runs/<RUN_ID>/data/audio/`
- **Format**: `.ogg` files with Spinoco recording IDs
- **Metadata**: `manifest.json`, `metrics.json`

### Transcribed Text
- **Location**: `steps/transcribe_asr_adapter/output/runs/<RUN_ID>/data/transcriptions/`
- **Format**: `.json` files with full transcript and metadata
- **Quality**: Confidence scores, timing, word-level data

### Anonymized Output
- **Location**: `steps/anonymize/output/runs/<RUN_ID>/data/anonymized/`
- **Format**: Numbered `.txt` files with sensitive data removed
- **Ready for**: Further AI processing, analysis, training

## 🔒 Data Privacy

**Anonymization Features:**
- Phone numbers: `+420123456789` → `@PHONE_001`
- Email addresses: `user@domain.com` → `@EMAIL_001`
- IBAN numbers: `CZ123456789` → `@IBAN_001`
- Call IDs preserved for traceability
- Vault mapping for reversible anonymization

## 🎯 Technical Details

**Spinoco Integration:**
- Production API with proper authentication
- Incremental download with state tracking
- Error handling and retry mechanisms
- Rate limiting and parallel processing

**Whisper Processing:**
- Large-v3 model for maximum quality
- Czech language optimization
- Technical terminology support
- GPU acceleration when available

**State Management:**
- SQLite database for idempotent processing
- Run tracking with unique IDs
- Error logging and retry capabilities
- Progress monitoring and metrics

## 🏃 Performance

**Processing Speed:**
- Download: ~1-2 recordings/second
- Transcription: ~2-3x real-time (45s for 2min audio)
- Anonymization: ~100 transcripts/second
- Parallel processing: 2-4 files simultaneously

**Resource Usage:**
- RAM: ~4-8GB for Whisper processing
- Storage: ~1MB per minute of audio
- Network: Direct API calls to Spinoco

## 🔗 Integration

**Designed for:**
- Production Spinoco call center
- Technical support analysis
- AI training data preparation
- Quality monitoring and reporting

**Output Compatibility:**
- Standard JSON format for transcripts
- Numbered text files for analysis
- Metadata preservation for traceability
- Error reporting for monitoring

---

**Production-ready Spinoco AI Pipeline** 🔥