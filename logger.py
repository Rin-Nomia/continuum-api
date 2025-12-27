"""
Z1 Data Logger - 資料記錄 + GitHub 備份
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
    """Z1 資料記錄器"""
    
    def __init__(self, log_dir='logs'):
        self.log_dir = log_dir
        
        # 建立資料夾
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 反饋資料夾
        self.feedback_dir = os.path.join(log_dir, 'feedback')
        if not os.path.exists(self.feedback_dir):
            os.makedirs(self.feedback_dir)
    
    def log(
        self,
        input_text: str,
        output_result: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """記錄一次分析"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'input': {
                'text': input_text,
                'length': len(input_text),
                'word_count': len(input_text.split()),
                'language': self._detect_language(input_text)
            },
            'output': {
                'freq_type': output_result.get('freq_type'),
                'confidence': output_result.get('confidence', {}).get('final'),
                'scenario': output_result.get('output', {}).get('scenario'),
                'repaired_text': output_result.get('output', {}).get('repaired_text'),
                'mode': output_result.get('mode')
            },
            'rhythm': {
                'rin_score': output_result.get('rhythm', {}).get('total'),
                'speed_index': output_result.get('rhythm', {}).get('speed_index'),
                'emotion_rate': output_result.get('rhythm', {}).get('emotion_rate')
            },
            'metadata': metadata or {}
        }
        
        # 寫入檔案
        date_str = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(self.log_dir, f'analysis_{date_str}.jsonl')
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        return entry
    
    def log_feedback(
        self,
        log_id: str,
        accuracy: int,
        helpful: int,
        accepted: bool
    ):
        """記錄用戶反饋"""
        feedback_entry = {
            'timestamp': datetime.now().isoformat(),
            'log_id': log_id,
            'accuracy': accuracy,
            'helpful': helpful,
            'accepted': accepted
        }
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        feedback_file = os.path.join(
            self.feedback_dir,
            f'feedback_{date_str}.jsonl'
        )
        
        with open(feedback_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(feedback_entry, ensure_ascii=False) + '\n')
    
    def _detect_language(self, text: str) -> str:
        """語言偵測"""
        if any('\u4e00' <= char <= '\u9fff' for char in text):
            return 'zh'
        if any('\u3040' <= char <= '\u30ff' for char in text):
            return 'ja'
        if any('\uac00' <= char <= '\ud7af' for char in text):
            return 'ko'
        return 'en'
    
    def get_stats(self) -> Dict[str, Any]:
        """取得統計"""
        total_analyses = 0
        tones = []
        scenarios = []
        languages = []
        confidences = []
        modes = []
        
        # 讀取分析記錄
        for log_file in os.listdir(self.log_dir):
            if log_file.endswith('.jsonl') and log_file.startswith('analysis_'):
                filepath = os.path.join(self.log_dir, log_file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            total_analyses += 1
                            tones.append(data['output']['freq_type'])
                            scenarios.append(data['output'].get('scenario', 'unknown'))
                            languages.append(data['input']['language'])
                            modes.append(data['output'].get('mode', 'unknown'))
                            
                            conf = data['output'].get('confidence')
                            if conf is not None:
                                confidences.append(conf)
                        except:
                            continue
        
        # 讀取反饋記錄
        total_feedback = 0
        accuracy_ratings = []
        helpful_ratings = []
        acceptance_count = 0
        
        if os.path.exists(self.feedback_dir):
            for feedback_file in os.listdir(self.feedback_dir):
                if feedback_file.endswith('.jsonl'):
                    filepath = os.path.join(self.feedback_dir, feedback_file)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                data = json.loads(line)
                                total_feedback += 1
                                accuracy_ratings.append(data['accuracy'])
                                helpful_ratings.append(data['helpful'])
                                if data['accepted']:
                                    acceptance_count += 1
                            except:
                                continue
        
        return {
            'analyses': {
                'total': total_analyses,
                'tone_distribution': dict(Counter(tones)),
                'scenario_distribution': dict(Counter(scenarios)),
                'language_distribution': dict(Counter(languages)),
                'mode_distribution': dict(Counter(modes)),
                'avg_confidence': (
                    sum(confidences) / len(confidences)
                    if confidences else 0
                )
            },
            'feedback': {
                'total': total_feedback,
                'avg_accuracy': (
                    sum(accuracy_ratings) / len(accuracy_ratings)
                    if accuracy_ratings else 0
                ),
                'avg_helpful': (
                    sum(helpful_ratings) / len(helpful_ratings)
                    if helpful_ratings else 0
                ),
                'acceptance_rate': (
                    acceptance_count / total_feedback
                    if total_feedback > 0 else 0
                )
            }
        }


class GitHubBackup:
    """GitHub 備份管理"""
    
    def __init__(self, log_dir='logs'):
        self.log_dir = log_dir
        self.gh_token = os.environ.get('GH_TOKEN')
        self.gh_repo = os.environ.get('GH_REPO')  # 格式: username/repo
        
        if not self.gh_token or not self.gh_repo:
            logger.warning("⚠️ GH_TOKEN or GH_REPO not set, backup disabled")
    
    def restore(self):
        """從 GitHub 恢復之前的 logs"""
        if not self.gh_token or not self.gh_repo:
            return
        
        try:
            # 如果 logs/ 已經存在且是 git repo，就 pull
            if os.path.exists(os.path.join(self.log_dir, '.git')):
                subprocess.run(
                    ['git', 'pull'],
                    cwd=self.log_dir,
                    capture_output=True
                )
                logger.info("✅ Pulled previous logs")
            else:
                # 否則 clone
                subprocess.run([
                    'git', 'clone',
                    f'https://{self.gh_token}@github.com/{self.gh_repo}.git',
                    self.log_dir
                ], capture_output=True)
                logger.info("✅ Cloned logs from GitHub")
        except Exception as e:
            logger.warning(f"⚠️ Restore failed: {e}")
    
    def backup(self):
        """備份 logs 到 GitHub"""
        if not self.gh_token or not self.gh_repo:
            return
        
        try:
            # 初始化 git（如果還沒）
            if not os.path.exists(os.path.join(self.log_dir, '.git')):
                subprocess.run(['git', 'init'], cwd=self.log_dir)
                subprocess.run(['git', 'config', 'user.name', 'Z1 API'], cwd=self.log_dir)
                subprocess.run(['git', 'config', 'user.email', 'api@z1.dev'], cwd=self.log_dir)
                subprocess.run([
                    'git', 'remote', 'add', 'origin',
                    f'https://{self.gh_token}@github.com/{self.gh_repo}.git'
                ], cwd=self.log_dir)
            
            # 提交
            subprocess.run(['git', 'add', '.'], cwd=self.log_dir)
            subprocess.run([
                'git', 'commit', '-m',
                f'Auto backup {datetime.now().isoformat()}'
            ], cwd=self.log_dir, capture_output=True)
            
            # 推送
            subprocess.run(
                ['git', 'push', '-u', 'origin', 'main', '--force'],
                cwd=self.log_dir,
                capture_output=True
            )
            
            logger.info("✅ Backup successful")
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
