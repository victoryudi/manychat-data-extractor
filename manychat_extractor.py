import pandas as pd
import requests
import os
import time
import logging
import sys
from typing import Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.traceback import install
from rich.table import Table
from pathlib import Path
import json
import asyncio
import aiohttp
from threading import Lock

# Install rich traceback handler
install(show_locals=True)

# Load environment variables
load_dotenv()

# Setup rich console
console = Console()

# Setup logging with rich handler
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, console=console)]
)

log = logging.getLogger("manychat_extractor")

@dataclass
class ManyChatData:
    email: str
    manychat_id: Optional[str] = None
    shopify_domain: Optional[str] = None
    telephone: Optional[str] = None
    processed_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)

class ExtractorStats:
    def __init__(self):
        self.total_processed = 0
        self.successful = 0
        self.failed = 0
        self.empty_responses = 0
        self.rate_limited = 0
        self.start_time = None
        self.end_time = None
        self.errors = []

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def print_summary(self):
        table = Table(title="Extraction Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Total Processed", str(self.total_processed))
        table.add_row("Successful", f"[green]{self.successful}[/green]")
        table.add_row("Failed", f"[red]{self.failed}[/red]")
        table.add_row("Empty Responses", f"[yellow]{self.empty_responses}[/yellow]")
        table.add_row("Rate Limited", f"[yellow]{self.rate_limited}[/yellow]")
        if self.duration:
            table.add_row("Duration", str(self.duration).split('.')[0])
        
        console.print(table)

        if self.errors:
            error_table = Table(title="Errors", show_header=True)
            error_table.add_column("Email", style="cyan")
            error_table.add_column("Error", style="red")
            
            for email, error in self.errors:
                error_table.add_row(email, str(error))
            
            console.print(error_table)

class RateLimiter:
    def __init__(self, max_requests: int, time_window: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = Lock()

    def acquire(self):
        with self.lock:
            now = time.time()
            
            # Remove old requests
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time <= self.time_window]
            
            if len(self.requests) >= self.max_requests:
                sleep_time = self.requests[0] + self.time_window - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self.requests = self.requests[1:]
            
            self.requests.append(now)

class ManyChatExtractor:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.api_url = 'https://api.manychat.com/fb/subscriber/findBySystemField'
        self.results = []
        self.stats = ExtractorStats()
        self.rate_limiter = RateLimiter(max_requests=10, time_window=1.0)
        self.results_lock = Lock()
        
        # Setup logging directory
        self.log_dir = Path('logs')
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup file handler for logging
        self.setup_file_logging()

    def setup_file_logging(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.log_dir / f'extraction_{timestamp}.log'
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        log.addHandler(file_handler)
        
        log.info(f"Logging to file: {log_file}")

    async def fetch_manychat_data_async(self, session: aiohttp.ClientSession, email: str) -> Optional[ManyChatData]:
        try:
            self.rate_limiter.acquire()
            
            log.info(f"🔍 Fetching data for email: {email}")
            
            headers = {
                'Authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json'
            }
            params = {'email': email}
            
            async with session.get(self.api_url, headers=headers, params=params) as response:
                if response.status == 429:  # Rate limit exceeded
                    log.warning("Rate limit reached. Cooling down for 10 seconds...")
                    self.stats.rate_limited += 1
                    await asyncio.sleep(10)
                    return await self.fetch_manychat_data_async(session, email)
                
                response.raise_for_status()
                data = await response.json()
                
                if data.get('status') == 'success':
                    result_data = data.get('data', {})
                    custom_fields = result_data.get('custom_fields', [])
                    
                    manychat_data = ManyChatData(
                        email=email,
                        manychat_id=result_data.get('id'),
                        shopify_domain=next((field['value'] for field in custom_fields 
                                           if field['name'] == 'shopify_domain'), None),
                        telephone=next((field['value'] for field in custom_fields 
                                             if field['name'] == 'telephone'), None),
                        processed_at=datetime.now().isoformat()
                    )
                    
                    log.info(f"Retrieved data for {email}: {json.dumps(manychat_data.to_dict(), indent=2)}")
                    with self.results_lock:
                        self.stats.successful += 1
                    return manychat_data
                
                log.warning(f"No data found for email: {email}")
                with self.results_lock:
                    self.stats.empty_responses += 1
                return ManyChatData(email=email, processed_at=datetime.now().isoformat())
                
        except Exception as e:
            log.error(f"❌ Error fetching data for {email}: {str(e)}", exc_info=True)
            with self.results_lock:
                self.stats.failed += 1
                self.stats.errors.append((email, str(e)))
            return ManyChatData(email=email, processed_at=datetime.now().isoformat())

    async def process_batch_async(self, session: aiohttp.ClientSession, emails: List[str]) -> List[ManyChatData]:
        tasks = [self.fetch_manychat_data_async(session, email) for email in emails]
        return await asyncio.gather(*tasks)

    def save_progress(self, data: List[ManyChatData], output_file: str):
        """Save current progress to CSV file"""
        df = pd.DataFrame([d.to_dict() for d in data])
        df.to_csv(output_file, index=False)
        log.info(f"Progress saved to {output_file}")
    
    async def process_csv_async(self, input_file: str, output_file: str = None, resume: bool = False):
        self.stats.start_time = datetime.now()
        log.info(f"Starting extraction process at {self.stats.start_time}")
        
        try:
            # Generate output filename if not provided
            if output_file is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = f'manychat_data_{timestamp}.csv'

            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Read input CSV
            log.info(f"Reading input file: {input_file}")
            input_df = pd.read_csv(input_file)
            
            if 'email' not in input_df.columns:
                raise ValueError("CSV must contain an 'email' column")

            # Load existing progress if resuming
            processed_emails = set()
            if resume and os.path.exists(output_file):
                existing_df = pd.read_csv(output_file)
                processed_emails = set(existing_df['email'].tolist())
                self.results = [ManyChatData(**row) for _, row in existing_df.iterrows()]
                log.info(f"Resuming from previous run. {len(processed_emails)} emails already processed")

            # Filter out already processed emails
            emails_to_process = [
                email.strip().lower() for email in input_df['email'].tolist()
                if email.strip().lower() not in processed_emails
            ]

            total_emails = len(emails_to_process)
            log.info(f"Found {total_emails} emails to process")
            
            # Process in batches of 10 emails
            batch_size = 10
            
            async with aiohttp.ClientSession() as session:
                with Progress(
                    SpinnerColumn(),
                    *Progress.get_default_columns(),
                    TimeElapsedColumn(),
                    console=console
                ) as progress:
                    task = progress.add_task("Processing emails...", total=total_emails)
                    
                    for i in range(0, total_emails, batch_size):
                        batch = emails_to_process[i:i + batch_size]
                        batch_results = await self.process_batch_async(session, batch)
                        
                        self.results.extend(batch_results)
                        self.stats.total_processed += len(batch_results)
                        
                        # Save progress after each batch
                        self.save_progress(self.results, output_file)
                        
                        # Update progress
                        progress.update(task, advance=len(batch))
            
            self.stats.end_time = datetime.now()
            log.info(f"Extraction completed at {self.stats.end_time}")
            
            # Print summary
            console.print("\n[bold green]Extraction Complete![/bold green]")
            self.stats.print_summary()
            
            return output_file
            
        except Exception as e:
            log.error("Fatal error during processing", exc_info=True)
            self.stats.end_time = datetime.now()
            self.stats.print_summary()
            
            # Save progress on error
            if self.results:
                error_output = f"error_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                self.save_progress(self.results, error_output)
                log.info(f"Partial results saved to: {error_output}")
            
            raise

def main():
    console.print("[bold blue]ManyChat Data Extractor[/bold blue]")
    console.print("=" * 50)
    
    try:
        # Get ManyChat API token from environment variable
        api_token = os.getenv('MANYCHAT_API_TOKEN')
        if not api_token:
            raise ValueError("MANYCHAT_API_TOKEN environment variable is not set")
        
        # Initialize extractor
        extractor = ManyChatExtractor(api_token)
        
        # Get input file from command line argument or prompt
        input_file = input("Enter the path to your input CSV file: ").strip()
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        # Ask about output file and generate default if needed
        output_file = input("Enter the path to your output CSV file (or press Enter for auto-generated): ").strip()
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'manychat_data_{timestamp}.csv'
            console.print(f"Using auto-generated output file: {output_file}")
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        # Ask about resuming only if the output file exists
        resume = False
        if os.path.exists(output_file):
            resume = input("Output file exists. Resume from previous run? (y/n): ").lower().startswith('y')
        
        # Process the file
        output_file = asyncio.run(extractor.process_csv_async(input_file, output_file, resume))
        
        console.print(f"\n[bold green]✨ Output saved to:[/bold green] {output_file}")
        
    except Exception as e:
        console.print(f"\n[bold red]ERROR:[/bold red] {str(e)}")
        log.error("Program terminated with error", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()