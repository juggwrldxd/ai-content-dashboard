#!/usr/bin/env python3
"""
generate_ideas.py — Generate 3 daily post ideas per model.

Reads persona from config.yaml and generates content ideas including
image references, captions, hashtags, best platform, and posting time.

PHASE 1 (current): Placeholder mode — generates templated ideas based on
persona descriptions, no API key required. Shows setup instructions for
when you're ready to connect a real LLM (Groq/OpenAI).

PHASE 2 (future): When GROQ_API_KEY or OPENAI_API_KEY is set in env or
config.yaml, this will call the LLM for dynamically generated ideas.

Output: 02_content/daily_ideas/{model}_daily_ideas.json
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path.home() / "ai_content_business"
CONFIG_PATH = BASE / "config.yaml"
OUTPUT_DIR = BASE / "02_content" / "daily_ideas"

# ─── Default persona templates (used when config.yaml personae are empty) ───
PERSONA_TEMPLATES = {
    "annie": {
        "name": "Annie",
        "persona": "College Girl / Insta Baddie — 19, arts student, lives in LA, posts fit checks and skincare. Sweet but flirty energy.",
        "vibe": ["college dorm", "gym mirror selfie", "coffee shop OOTD", "sunset rooftop", "beach day"],
        "caption_styles": ["casual & relatable", "playful tease", "confidence boost", "late night thoughts"],
        "hashtag_pool": ["#collegegirl", "#ootd", "#fitcheck", "#skincare", "#lifestyle", "#selfie", "#hotgirlsummer", "#glowup"],
    },
    "yesha": {
        "name": "Yesha",
        "persona": "Curvy / Thick Model — 22, works as a bartender, loves body positivity and workout content. Bold, confident, direct.",
        "vibe": ["gym pump", "lingerie try-on", "confident mirror", "night out", "bedroom tease"],
        "caption_styles": ["body positive", "boss energy", "sensual tease", "workout grind"],
        "hashtag_pool": ["#thickthighs", "#bodypositive", "#curvygirl", "#gymmotivation", "#thickmodel", "#bbl", "#booty", "#fitness"],
    },
    "jasmine": {
        "name": "Jasmine",
        "persona": "Alternative / Tattoo Baddie — 21, barista, punk vibes. Dark aesthetic, piercings, edgy style. Cool and mysterious.",
        "vibe": ["tattoo reveal", "alt fashion", "dark bedroom", "band tee OOTD", "rainy street"],
        "caption_styles": ["edgy and mysterious", "sarcastic", "deep quote", "anti-mainstream"],
        "hashtag_pool": ["#altgirl", "#tattooedgirls", "#edgy", "#darkaesthetic", "#piercings", "#alternative", "#goth", "#rebel"],
    },
}

# ─── Cache hours for each idea set ────
BEST_TIMES = {
    "X": ["06:00 PM UTC", "08:00 PM UTC", "10:00 PM UTC"],
    "Telegram": ["09:00 AM UTC", "12:00 PM UTC", "06:00 PM UTC"],
    "Reddit": ["07:00 AM UTC", "02:00 PM UTC", "09:00 PM UTC"],
}


def load_config():
    """Load config.yaml — returns dict or {} if missing/invalid."""
    if not CONFIG_PATH.exists():
        print("⚠️  config.yaml not found. Using default persona templates.")
        return {"models": {}}

    try:
        import yaml
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        print("⚠️  PyYAML not installed. Install with: pip install pyyaml")
        print("   Falling back to manual config parse.\n")
        return _parse_config_fallback()
    except Exception as e:
        print(f"⚠️  Error reading config.yaml: {e}")
        return {"models": {}}


def _parse_config_fallback():
    """Minimal YAML-free parser for config.yaml."""
    models = {}
    current_model = None
    try:
        with open(CONFIG_PATH) as f:
            for line in f:
                line = line.rstrip()
                if line.startswith("  "):
                    if current_model and ":" in line:
                        key, _, val = line.partition(":")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key == "persona" and current_model:
                            models.setdefault(current_model, {})["persona"] = val
                elif line.startswith("models:"):
                    continue
                elif not line.startswith(" ") and line.rstrip().endswith(":") and line[0] != "#":
                    for m in ("annie", "yesha", "jasmine"):
                        if line.strip().startswith(m):
                            current_model = m
                            models.setdefault(current_model, {})
                            break
    except Exception:
        pass
    return {"models": models}


def get_persona(model_name, config):
    """Get persona string for a model, falling back to template."""
    model_config = config.get("models", {}).get(model_name, {})
    persona_str = model_config.get("persona", "")

    if persona_str and persona_str.strip():
        return persona_str.strip()

    # Fall back to template
    template = PERSONA_TEMPLATES.get(model_name)
    if template:
        return template["persona"]
    return f"Generic model persona for {model_name}"


def generate_idea(model_name, persona, idea_index, date):
    """Generate one placeholder post idea based on persona template."""
    template = PERSONA_TEMPLATES.get(model_name)
    if not template:
        template = {
            "name": model_name.capitalize(),
            "vibe": ["portrait", "lifestyle", "tease"],
            "caption_styles": ["casual"],
            "hashtag_pool": ["#model", "#beautiful"],
        }

    vibe = random.choice(template["vibe"])
    style = random.choice(template["caption_styles"])
    hashtags = random.sample(
        template["hashtag_pool"], min(4, len(template["hashtag_pool"]))
    )

    # Pick a random best platform and time
    platform = random.choice(["X", "Telegram", "Reddit"])
    time = random.choice(BEST_TIMES.get(platform, ["12:00 PM UTC"]))

    # Create caption based on style
    captions_by_style = {
        "casual & relatable": f"just woke up feeling myself today 🥰 who else needs more coffee?",
        "playful tease": f"bet you can't guess what i'm wearing under this 😏",
        "confidence boost": f"learning to love every curve. you should too 💋",
        "late night thoughts": f"it's 2am and i'm thinking about… you?",
        "body positive": f"thick thighs save lives 🤷‍♀️ love what you've got!",
        "boss energy": f"i don't chase, i attract. simple as that 👑",
        "sensual tease": f"some things look better in the dark… want to see?",
        "workout grind": f"leg day never skips me 💪 who's keeping up?",
        "edgy and mysterious": f"i'm not for everyone. and i'm okay with that.🖤",
        "sarcastic": f"oh you're into me? how original 🙄",
        "deep quote": f"the darker the night, the brighter the stars. ✨",
        "anti-mainstream": f"basic is boring. glad you found me instead. 🦇",
        "casual": f"just another day being me 💕",
    }
    caption = captions_by_style.get(style, captions_by_style["casual"])

    # Image reference
    image_ref = f"{model_name}/{model_name}_{date.replace('-', '')}_{idea_index + 1:02d}.png"

    return {
        "id": f"{model_name}_{date}_{idea_index + 1}",
        "model": model_name,
        "date": date,
        "image_reference": image_ref,
        "image_description": f"A {vibe} shot with {style} energy",
        "caption": caption,
        "hashtags": hashtags,
        "best_platform": platform,
        "best_time": time,
        "caption_style": style,
        "vibe": vibe,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def show_setup_instructions():
    """Print instructions for connecting a real LLM."""
    print("=" * 60)
    print("📋 PHASE 2 SETUP — Connect a Real LLM")
    print("=" * 60)
    print("""
To generate AI-powered ideas instead of placeholders:

1. Groq (recommended — fast & free tier available)
   - Sign up at https://console.groq.com
   - Get your API key
   - Set in config.yaml under a new section:
       llm:
         provider: groq
         api_key: "gsk_your_key_here"
         model: "mixtral-8x7b-32768"  # or "llama-3.3-70b-versatile"
   - Or set env var:  export GROQ_API_KEY="gsk_your_key_here"

2. OpenAI
   - Set in config.yaml:
       llm:
         provider: openai
         api_key: "sk-your-key"
         model: "gpt-4o-mini"
   - Or set env var:  export OPENAI_API_KEY="sk-your-key"

3. When either key is detected and providers are imported,
   this script will call the LLM with a prompt like:
   "Generate 3 post ideas for {model} ({persona}) for {date}"

   The prompt includes persona description, platform preferences,
   and asks for image description + caption + hashtags per idea.

Install required packages:
    pip install pyyaml openai groq
""")


def main():
    print("💡 AI Content Business — Daily Idea Generator")
    print("=" * 50)

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Load config
    config = load_config()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Model names from config or fallback
    model_names = list(config.get("models", {}).keys()) or ["annie", "yesha", "jasmine"]

    all_ideas = {}

    for model_name in model_names:
        if not model_name.strip():
            continue
        model_name = model_name.strip().lower()

        persona = get_persona(model_name, config)

        print(f"\n📸 Generating ideas for: {model_name.capitalize()}")
        print(f"   Persona: {persona[:60]}{'...' if len(persona) > 60 else ''}")

        ideas = []
        for i in range(3):
            idea = generate_idea(model_name, persona, i, date)
            ideas.append(idea)
            print(f"   [{i + 1}/3] {idea['caption'][:50]}... → {idea['best_platform']} @ {idea['best_time']}")

        # Save per-model file
        output_file = OUTPUT_DIR / f"{model_name}_daily_ideas.json"
        output_data = {
            "model": model_name,
            "persona": persona,
            "date": date,
            "ideas": ideas,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mode": "placeholder",
        }
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"   ✅ Saved to {output_file.relative_to(BASE)}")

        all_ideas[model_name] = ideas

    # Save combined daily ideas file too
    combined_file = OUTPUT_DIR / f"all_models_{date}.json"
    with open(combined_file, "w") as f:
        json.dump({
            "date": date,
            "models": all_ideas,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mode": "placeholder",
            "message": "These are placeholder ideas. Set up an LLM API key for AI-generated ideas.",
        }, f, indent=2)
    print(f"\n✅ Combined saved to {combined_file.relative_to(BASE)}")

    # Print setup instructions if no API key is configured
    has_api = any(k in os.environ for k in ["GROQ_API_KEY", "OPENAI_API_KEY"])
    if not has_api:
        show_setup_instructions()
    else:
        print("\n🔑 LLM API key detected in environment — ready for Phase 2 upgrade!")

    print("\n✅ Done.")


if __name__ == "__main__":
    main()