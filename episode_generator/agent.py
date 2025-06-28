from typing import Dict, Any, Optional
from google.adk.agents import Agent
import os
from dotenv import load_dotenv

import json
import logging
from vertexai.generative_models import GenerativeModel, Part
import vertexai

# Load environment variables
load_dotenv()

# Initialize Vertex AI with values from environment
project_id = os.getenv("GCP_CLOUD_PROJECT")
location = os.getenv("GOOGLE_CLOUD_LOCATION")
vertexai.init(project=project_id, location=location)


logger = logging.getLogger(__name__)
MODEL_NAME = "gemini-1.5-flash"


def objective_analyzer(media_uri: str, mime_type: str) -> dict:
    """Extract objective facts from media files"""
    model = GenerativeModel(MODEL_NAME)
    try:
        media_part = Part.from_uri(uri=media_uri, mime_type=mime_type)

        prompt = """
        あなたは、子供の行動を観察する客観的な分析システムです。
        この画像/動画から観察できる全ての客観的な事実をリストアップしてください。

        【厳守事項】
        - 観察された事実のみを記述し、解釈や感想は含めないでください
        - 年齢や月齢の推測は行わないでください
        - JSONのみを返してください

        {
            "all_observed_actions": ["観察された全ての行動のリスト"],
            "observed_emotions": ["表情から読み取れる感情のリスト"],
            "spoken_words": ["聞き取れた発話内容（ある場合）"],
            "environment": "場所や環境の客観的な描写",
            "physical_interactions": ["物理的な相互作用（触る、持つ、指差すなど）"],
            "body_movements": ["体の動き（歩く、座る、手を振るなど）"]
        }
        """

        response = model.generate_content([media_part, prompt])
        response_text = response.text.strip()

        logger.info(f"Raw response from model: {response_text[:200]}...")

        import re

        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

        response_text = response_text.strip()

        if not response_text:
            logger.error("Empty response from model")
            return {"status": "error", "error_message": "Empty response from model"}

        try:
            facts = json.loads(response_text)
            return {"status": "success", "report": facts}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                "status": "error",
                "error_message": f"Failed to parse JSON: {str(e)}",
            }

    except Exception as e:
        return {"status": "error", "error_message": str(e)}


def highlight_identifier(facts: Dict[str, Any]) -> dict:
    """Identify highlight moments from objective facts"""
    model = GenerativeModel(MODEL_NAME)
    try:
        facts_json = json.dumps(facts, ensure_ascii=False, indent=2)

        prompt = f"""
        あなたは、子供の成長記録から最も記憶に残る「ハイライトシーン」を見つけ出すプロのドキュメンタリー映像編集者です。

        以下の客観的な事実データから、最も感情豊かで、子供の個性や成長が感じられる「ハイライト」と呼べる瞬間を一つだけ特定してください。

        【事実データ】
        {facts_json}

        【選定基準】
        - 子供の感情が最も豊かに表れている瞬間
        - 発達や成長が感じられる行動
        - 親にとって記憶に残りそうな特別な瞬間

        以下のJSON形式で、ハイライトシーンの情報を返してください：
        {{
            "highlight_moment_title": "ハイライトシーンのタイトル（15文字以内）",
            "highlight_description": "なぜこの瞬間をハイライトとして選んだかの説明",
            "relevant_actions": ["ハイライトに関連する具体的な行動"],
            "relevant_emotion": "ハイライトシーンでの主な感情",
            "spoken_words_in_highlight": ["ハイライトシーンでの発話（ある場合）"],
            "development_indicators": ["このハイライトが示す発達の兆候"]
        }}
        """

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        import re

        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

        highlight = json.loads(response_text)
        return {"status": "success", "report": highlight}

    except Exception as e:
        return {"status": "error", "error_message": str(e)}


def story_generator(
    facts: Dict[str, Any],
    highlight: Dict[str, Any],
    child_age_months: Optional[int] = None,
) -> dict:
    """Generate heartwarming stories from highlight moments"""
    model = GenerativeModel(MODEL_NAME)
    try:
        facts_json = json.dumps(facts, ensure_ascii=False, indent=2)
        highlight_json = json.dumps(highlight, ensure_ascii=False, indent=2)

        age_context = ""
        if child_age_months:
            age_context = f"\n子供の月齢: {child_age_months}ヶ月"

        prompt = f"""
        あなたは、子供の成長記録を温かい物語として伝える作家です。
        以下の客観的な事実とハイライトシーンから、親の心に響く短い物語を作成してください。

        【観察された事実】
        {facts_json}

        【ハイライトシーン】
        {highlight_json}
        {age_context}

        【作成指針】
        - 客観的事実に基づきながら、温かみのある表現を使う
        - 子供の成長や個性を感じられる内容にする
        - 親が読んで幸せな気持ちになれる文章にする
        - もし月齢が提供されている場合は、その発達段階に合わせた視点を加える

        以下のJSON形式で物語を返してください：
        {{
            "story_title": "物語のタイトル（20文字以内）",
            "story_content": "温かい物語（200-300文字）",
            "parent_message": "親へのメッセージ（50-100文字）",
            "growth_keywords": ["この物語から感じられる成長のキーワード3つ"],
            "emotion_theme": "物語の感情的なテーマ（喜び、驚き、感動、成長など）"
        }}
        """

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        import re

        json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

        story = json.loads(response_text)
        return {"status": "success", "report": story}

    except Exception as e:
        return {"status": "error", "error_message": str(e)}


root_agent = Agent(
    name="episode_generator_agent",
    model=MODEL_NAME,
    description="Agent to generate an episode from a media file.",
    instruction="You are an agent that generates an episode from a media file by analyzing it, finding a highlight, and creating a story.",
    tools=[objective_analyzer, highlight_identifier, story_generator],
)
