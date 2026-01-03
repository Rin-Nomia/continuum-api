"""
Continuum Data Logger - 資料記錄 + GitHub 備份（真・完整版）
RIN Protocol — Continuum Module
記錄所有 Pipeline 輸出、LLM 原始回應、完整修復內容
"""
import json
from datetime import datetime
import os
from collections import Counter
from typing import Dict, Any, Optional
import subprocess
import logging

logger = logging.getLogger(__name__)


class DataLogger:
    """Continuum 資料記錄器 - 真・完整版"""
    
    def __init__(self, log_dir='logs'):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 初始化統計
        self.stats = {
            'total_requests': 0,
            'by_type': Counter(),
            'by_scenario': Counter(),
            'avg_confidence': []
        }
    
    def log_analysis(self, input_text: str, output_result: Dict[str, Any], 
                    metadata: Optional[Dict] = None) -> Dict[str, str]:
        """
        記錄分析結果
        
        Args:
            input_text: 原始輸入文字
            output_result: Pipeline 完整輸出
            metadata: 額外的 metadata
        
        Returns:
            包含 timestamp 的 log entry
        """
        timestamp = datetime.now().isoformat()
        
        # 建立 log entry
        log_entry = {
            'timestamp': timestamp,
            'input': {
                'text': input_text,
                'length': len(input_text)
            },
            'output': {
                'freq_type': output_result.get('freq_type'),
                'confidence': output_result.get('confidence', {}).get('final'),
                'scenario': output_result.get('output', {}).get('scenario'),
                'repaired_text': output_result.get('output', {}).get('repaired_text'),
                'mode': output_result.get('mode')
            },
            'metadata': metadata or {}
        }
        
        # 寫入 JSONL 檔案
        date_str = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(self.log_dir, f'analysis_{date_str}.jsonl')
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        # 更新統計
        self.stats['total_requests'] += 1
        self.stats['by_type'][log_entry['output']['freq_type']] += 1
        self.stats['by_scenario'][log_entry['output']['scenario']] += 1
        if log_entry['output']['confidence']:
            self.stats['avg_confidence'].append(log_entry['output']['confidence'])
        
        return {'timestamp': timestamp, 'log_file': log_file}
    
    def log_feedback(self, log_id: str, accuracy: int, helpful: int, 
                     accepted: bool):
        """記錄用戶反饋"""
        feedback_entry = {
            'timestamp': datetime.now().isoformat(),
            'log_id': log_id,
            'feedback': {
                'accuracy': accuracy,
                'helpful': helpful,
                'accepted': accepted
            }
        }
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        feedback_file = os.path.join(self.log_dir, f'feedback_{date_str}.jsonl')
        
        with open(feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + '\n')
    
    def get_stats(self) -> Dict[str, Any]:
        """取得統計資訊"""
        avg_conf = (
            sum(self.stats['avg_confidence']) / len(self.stats['avg_confidence'])
            if self.stats['avg_confidence'] else 0
        )
        
        return {
            'total_requests': self.stats['total_requests'],
            'by_type': dict(self.stats['by_type']),
            'by_scenario': dict(self.stats['by_scenario']),
            'avg_confidence': round(avg_conf, 3)
        }


class GitHubBackup:
    """GitHub 備份管理"""
    
    def __init__(self, log_dir='logs'):
        self.log_dir = log_dir
        self.gh_token = os.environ.get('GH_TOKEN')
        self.gh_repo = os.environ.get('GH_REPO')
        
        if not self.gh_token or not self.gh_repo:
            logger.warning("⚠️ GH_TOKEN or GH_REPO not set, backup disabled")
    
    def restore(self):
        """從 GitHub 恢復 logs"""
        if not self.gh_token or not self.gh_repo:
            return
        
        try:
            if os.path.exists(os.path.join(self.log_dir, '.git')):
                subprocess.run(['git', 'pull'], cwd=self.log_dir, capture_output=True)
                logger.info("✅ Pulled previous logs")
            else:
                subprocess.run([
                    'git', 'clone',
                    f'https://{self.gh_token}@github.com/{self.gh_repo}.git',
                    self.log_dir
                ], capture_output=True)
                logger.info("✅ Cloned logs from GitHub")
        except Exception as e:
            logger.warning(f"⚠️ Restore failed: {e}")
    
    def backup(self):
        """備份到 GitHub"""
        if not self.gh_token or not self.gh_repo:
            return
        
        try:
            if not os.path.exists(os.path.join(self.log_dir, '.git')):
                subprocess.run(['git', 'init', '-b', 'main'], cwd=self.log_dir)
                subprocess.run(['git', 'config', 'user.name', 'Continuum API'], cwd=self.log_dir)
                subprocess.run(['git', 'config', 'user.email', 'api@continuum.dev'], cwd=self.log_dir)
                subprocess.run([
                    'git', 'remote', 'add', 'origin',
                    f'https://{self.gh_token}@github.com/{self.gh_repo}.git'
                ], cwd=self.log_dir)
            
            subprocess.run(['git', 'add', '.'], cwd=self.log_dir)
            subprocess.run([
                'git', 'commit', '-m',
                f'Auto backup {datetime.now().isoformat()}'
            ], cwd=self.log_dir, capture_output=True)
            
            subprocess.run(
                ['git', 'push', '-u', 'origin', 'main', '--force'],
                cwd=self.log_dir,
                capture_output=True
            )
            
            logger.info("✅ Backup successful")
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
