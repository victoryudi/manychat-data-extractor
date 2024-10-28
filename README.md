<div align="center">

# 🚀 ManyChat Data Extractor

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Made with ManyChat API](https://img.shields.io/badge/Made%20with-ManyChat%20API-orange.svg)](https://manychat.com)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A high-performance, asynchronous data extraction tool for ManyChat that processes user data in parallel while respecting API rate limits.

[Features](#features) •
[Installation](#installation) •
[Usage](#usage) •
[Configuration](#configuration) •
[Contributing](#contributing)

</div>

## ✨ Features

- **⚡ High Performance**: Process up to 10 requests per second with async operations
- **📊 Smart Rate Limiting**: Automatic handling of API rate limits
- **💾 Auto-Save Progress**: Saves data after every batch
- **🔄 Resume Capability**: Continue from where you left off
- **📝 Detailed Logging**: Comprehensive logs with rich formatting
- **🎯 Error Handling**: Robust error recovery with backup saves
- **📈 Live Progress**: Real-time progress tracking with status bar
- **📋 Summary Stats**: Detailed extraction statistics and error reporting

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/victoryudi/manychat-data-extractor.git
cd manychat-data-extractor
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # For Unix/macOS
venv\Scripts\activate     # For Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## 🔧 Configuration

1. Create a `.env` file in the project root:
```env
MANYCHAT_API_TOKEN=your_api_token_here
```

2. Make sure your input CSV file has an `email` column with the emails you want to process

[Previous sections remain the same until Usage...]

## 💻 Usage

### Running the Extractor
```bash
python manychat_extractor.py
```

The script will prompt you for:
- Input CSV file path
- Output CSV file path (optional)
- Whether to resume a previous run (if applicable)

### 🔧 Customizing ManyChat Fields

The extractor currently fetches these custom fields from ManyChat:
- `shopify_domain`
- `telefone`

To modify which fields are extracted:

1. Update the `ManyChatData` class in `manychat_extractor.py`:
```python
@dataclass
class ManyChatData:
    email: str
    manychat_id: Optional[str] = None
    # Add your custom fields here
    your_field_name: Optional[str] = None
    another_field: Optional[str] = None
    processed_at: Optional[str] = None
```

2. Modify the field extraction in the `fetch_manychat_data_async` method:
```python
manychat_data = ManyChatData(
    email=email,
    manychat_id=result_data.get('id'),
    # Add your custom field extraction here
    your_field_name=next((field['value'] for field in custom_fields 
                         if field['name'] == 'your_field_name'), None),
    another_field=next((field['value'] for field in custom_fields 
                       if field['name'] == 'another_field'), None),
    processed_at=datetime.now().isoformat()
)
```

#### Example: Adding a 'Phone' Field

```python
# In ManyChatData class:
@dataclass
class ManyChatData:
    email: str
    manychat_id: Optional[str] = None
    phone: Optional[str] = None  # Add new field
    processed_at: Optional[str] = None

# In fetch_manychat_data_async method:
manychat_data = ManyChatData(
    email=email,
    manychat_id=result_data.get('id'),
    phone=next((field['value'] for field in custom_fields 
                if field['name'] == 'phone'), None),  # Extract phone field
    processed_at=datetime.now().isoformat()
)
```

#### Finding Available Fields

To see all available custom fields for a subscriber:

1. Add this debug log in `fetch_manychat_data_async`:
```python
if data.get('status') == 'success':
    result_data = data.get('data', {})
    custom_fields = result_data.get('custom_fields', [])
    
    # Add this debug log
    log.debug(f"Available custom fields: {json.dumps([
        {'name': field['name'], 'value': field['value']} 
        for field in custom_fields
    ], indent=2)}")
```

2. Set logging level to DEBUG in your `.env`:
```env
MANYCHAT_API_TOKEN=your_api_token_here
LOG_LEVEL=DEBUG
```

This will show all available custom fields in your logs for reference.

[Continue with previous sections...]

Run the extractor:
```bash
python manychat_extractor.py
```

The script will prompt you for:
- Input CSV file path
- Output CSV file path (optional)
- Whether to resume a previous run (if applicable)

### Output Data Structure

The extractor retrieves the following data for each email:

```python
{
    "email": "user@example.com",
    "manychat_id": "123456",
    "telefone": "+1234567890",
    "processed_at": "2024-10-28T15:30:00"
}
```

## 📊 Sample Output

```bash
ManyChat Data Extractor
==================================================
Enter the path to your input CSV file: users.csv
Using auto-generated output file: manychat_data_20241028_153000.csv

⠋ Processing emails... ━━━━━━━━━━━━━━━━━━━━━━ 45% 0:01:23

Extraction Summary
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Metric          ┃ Value   ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ Total Processed │ 100     │
│ Successful      │ 98      │
│ Failed          │ 0       │
│ Empty Responses │ 2       │
│ Rate Limited    │ 1       │
│ Duration        │ 0:02:15 │
└─────────────────┴─────────┘
```

## 🔄 Background Processing

The extractor uses:
- Async/await with `aiohttp` for concurrent requests
- Thread-safe rate limiting
- Automatic retry on rate limit exceeded
- Progress saving after each batch
- Comprehensive error handling

## 📁 Project Structure

```
manychat-data-extractor/
├── manychat_extractor.py  # Main script
├── requirements.txt       # Dependencies
├── .env                  # Configuration
└── logs/                 # Log files
```

## 🤝 Contributing

Contributions are welcome! Feel free to:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/improvement`)
3. Make your changes
4. Commit your changes (`git commit -am 'Add new feature'`)
5. Push to the branch (`git push origin feature/improvement`)
6. Create a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [ManyChat API](https://manychat.com/api-documentation) for the platform
- [aiohttp](https://docs.aiohttp.org/) for async HTTP requests
- [Rich](https://rich.readthedocs.io/) for beautiful terminal formatting

---

<div align="center">

Created with ❤️ by [victoryudi](https://github.com/victoryudi)

</div>