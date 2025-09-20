"""
Email Text Cleaner - Extract clean, readable text from Gmail API responses

Adapted from the improved email cleaning implementation to integrate
with the search_email task pipeline.
"""

import re
import html
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from server.logging_config import logger


class EmailTextCleaner:
    """Clean and extract readable text from Gmail API email responses"""
    
    def __init__(self, max_url_length: int = 60):
        """Initialize the email text cleaner"""
        self.max_url_length = max_url_length
        
        # Elements to completely remove
        self.remove_elements = [
            'style', 'script', 'meta', 'link', 'title', 'head',
            'noscript', 'iframe', 'embed', 'object', 'img'
        ]
        
        # Elements that typically contain noise
        self.noise_elements = [
            'footer', 'header', '.footer', '.header', 
            '[class*="footer"]', '[class*="header"]',
            '[class*="tracking"]', '[class*="pixel"]',
            '[style*="display:none"]', '[style*="display: none"]'
        ]

    def clean_html_email(self, html_content: str) -> str:
        """
        Extract clean text from HTML email content
        
        Args:
            html_content: Raw HTML email content
            
        Returns:
            Clean, readable text
        """
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements completely
            for element_type in self.remove_elements:
                for element in soup.find_all(element_type):
                    element.decompose()
            
            # Remove noise elements using CSS selectors
            for selector in self.noise_elements:
                try:
                    for element in soup.select(selector):
                        element.decompose()
                except Exception as e:
                    logger.debug(f"Could not remove element with selector {selector}: {e}")
            
            # Convert links to readable format with URL truncation
            for link in soup.find_all('a'):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                if href:
                    # Truncate long URLs
                    display_url = self.truncate_url(href)
                    
                    if text and text != href and not self.is_url_like(text):
                        # Text is meaningful and different from URL
                        link.replace_with(f"{text} ({display_url})")
                    elif text and text != href:
                        # Text is also a URL, just show the truncated version
                        link.replace_with(f"[Link: {display_url}]")
                    else:
                        # No meaningful text, just show the URL
                        link.replace_with(f"[Link: {display_url}]")
            
            # Extract text and clean up
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up the extracted text
            text = self.post_process_text(text)
            
            return text
            
        except Exception as e:
            logger.error(f"Error cleaning HTML email: {e}")
            # Fallback: try to extract text with regex
            return self.fallback_text_extraction(html_content)

    def truncate_url(self, url: str) -> str:
        """Truncate a URL to make it more readable"""
        if not url or len(url) <= self.max_url_length:
            return url
        
        # Remove tracking parameters first
        url = self.remove_tracking_params(url)
        
        # Simple truncation
        if len(url) <= self.max_url_length:
            return url
        return url[:self.max_url_length] + "..."

    def remove_tracking_params(self, url: str) -> str:
        """
        Remove common tracking parameters from URLs
        
        Args:
            url: The URL to clean
            
        Returns:
            URL with tracking parameters removed
        """
        try:
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            
            parsed = urlparse(url)
            if not parsed.query:
                return url
            
            # Common tracking parameters
            tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'gclid', 'fbclid', 'ref', 'trk'}
            
            # Parse query parameters
            query_params = parse_qs(parsed.query, keep_blank_values=False)
            
            # Remove tracking parameters
            cleaned_params = {
                key: value for key, value in query_params.items()
                if key.lower() not in tracking_params
            }
            
            # Rebuild URL
            if cleaned_params:
                new_query = urlencode(cleaned_params, doseq=True)
                new_parsed = parsed._replace(query=new_query)
            else:
                new_parsed = parsed._replace(query='')
            
            return urlunparse(new_parsed)
            
        except Exception as e:
            logger.debug(f"Error removing tracking params: {e}")
            return url

    def is_url_like(self, text: str) -> bool:
        """
        Check if text looks like a URL
        
        Args:
            text: Text to check
            
        Returns:
            True if text looks like a URL
        """
        if not text:
            return False
        
        text = text.lower()
        return (text.startswith(('http://', 'https://', 'www.', 'ftp://')) or
                ('.' in text and len(text.split('.')) >= 2 and ' ' not in text))

    def post_process_text(self, text: str) -> str:
        """
        Post-process extracted text to improve readability
        
        Args:
            text: Extracted text from HTML
            
        Returns:
            Cleaned and formatted text
        """
        # Decode HTML entities
        text = html.unescape(text)
        
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Max 2 consecutive newlines
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces to single space
        text = re.sub(r'\n ', '\n', text)  # Remove spaces at start of lines
        
        # Remove common email noise patterns
        noise_patterns = [
            r'View this email in your browser.*?\n',
            r'If you can\'t see this email.*?\n',
            r'This is a system-generated email.*?\n',
            r'Please do not reply to this email.*?\n',
            r'Unsubscribe.*?preferences.*?\n',
            r'© \d{4}.*?All rights reserved.*?\n',
            r'\[Image:.*?\]',  # Remove image placeholders
            r'\[Image\]',  # Remove simple image placeholders
            r'<image>.*?</image>',  # Remove image tags in text
            r'\(image\)',  # Remove (image) references
            r'\(Image\)',  # Remove (Image) references
            r'Image: .*?\n',  # Remove "Image: description" lines
            r'Alt text: .*?\n',  # Remove alt text descriptions
        ]
        
        for pattern in noise_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Clean up final formatting
        text = text.strip()
        
        # Final pass: remove image URLs and truncate remaining URLs
        text = self.remove_image_urls(text)
        text = self.truncate_urls_in_text(text)
        
        return text

    def remove_image_urls(self, text: str) -> str:
        """
        Remove URLs that point to images
        
        Args:
            text: Text that may contain image URLs
            
        Returns:
            Text with image URLs removed
        """
        try:
            # Pattern to find image URLs
            image_url_patterns = [
                r'https?://[^\s\)]*\.(?:jpg|jpeg|png|gif|bmp|webp|svg)(?:\?[^\s\)]*)?',
                r'https?://[^\s\)]*(?:image|img|photo|picture)[^\s\)]*',
                r'\([^\)]*https?://[^\s\)]*\.(?:jpg|jpeg|png|gif|bmp|webp|svg)[^\)]*\)',  # URLs in parentheses
                r'\s*\(https?://[^\s\)]*\.(?:jpg|jpeg|png|gif|bmp|webp|svg)[^\)]*\)',  # Image URLs with spaces before parentheses
            ]
            
            for pattern in image_url_patterns:
                text = re.sub(pattern, '', text, flags=re.IGNORECASE)
            
            # Remove empty parentheses left behind
            text = re.sub(r'\(\s*\)', '', text)
            
            # Clean up extra whitespace
            text = re.sub(r'\n\s*\n', '\n', text)
            text = re.sub(r'  +', ' ', text)
            
            return text.strip()
            
        except Exception as e:
            logger.debug(f"Error removing image URLs: {e}")
            return text

    def truncate_urls_in_text(self, text: str) -> str:
        """
        Find and truncate URLs in plain text
        
        Args:
            text: Text that may contain URLs
            
        Returns:
            Text with URLs truncated
        """
        try:
            # Pattern to find URLs in text
            url_pattern = r'(https?://[^\s\)]+|www\.[^\s\)]+)'
            
            def truncate_match(match):
                url = match.group(1)
                return self.truncate_url(url)
            
            # Replace URLs with truncated versions
            text = re.sub(url_pattern, truncate_match, text)
            
            return text
            
        except Exception as e:
            logger.debug(f"Error truncating URLs in text: {e}")
            return text

    def fallback_text_extraction(self, html_content: str) -> str:
        """
        Fallback method to extract text using regex when BeautifulSoup fails
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            Extracted text
        """
        try:
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', html_content)
            
            # Decode HTML entities
            text = html.unescape(text)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            return text
            
        except Exception as e:
            logger.error(f"Fallback text extraction failed: {e}")
            return "Error: Could not extract text from email"

    def extract_attachment_info(self, attachments: List[Dict[str, Any]]) -> tuple[bool, int, List[str]]:
        """
        Extract attachment information from Gmail API response
        
        Args:
            attachments: List of attachment dictionaries from Gmail API
            
        Returns:
            Tuple of (has_attachments, attachment_count, attachment_filenames)
        """
        if not attachments:
            return False, 0, []
        
        filenames = []
        for attachment in attachments:
            if isinstance(attachment, dict):
                filename = attachment.get('filename', 'Unknown filename')
                mime_type = attachment.get('mimeType', 'Unknown type')
                filenames.append(f"{filename} ({mime_type})")
        
        return len(attachments) > 0, len(attachments), filenames

    def clean_email_content(self, message_data: Dict[str, Any]) -> str:
        """
        Main method to extract clean text from a Gmail API message
        
        Args:
            message_data: Single message data from Gmail API
            
        Returns:
            Clean, readable text content
        """
        # Try to get the main message text
        message_text = message_data.get('messageText', '')
        
        # Fallback to preview if no main text
        if not message_text:
            preview = message_data.get('preview', {})
            if isinstance(preview, dict):
                message_text = preview.get('body', '')
        
        # If we have content, clean it
        if message_text:
            clean_text = self.clean_html_email(message_text)
            
            # Truncate if too long (for LLM context management)
            if len(clean_text) > 2000:
                clean_text = clean_text[:2000] + "... [truncated]"
            
            return clean_text
        
        return "No content available"


__all__ = [
    "EmailTextCleaner",
]
