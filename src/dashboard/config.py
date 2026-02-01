# src/dashboard/config.py
import sys
import os

# 将项目根目录加入 python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import yaml
from pathlib import Path
from loguru import logger
import streamlit as st
from src.research_agent.agents.prompt.prompt_agent import PromptAgent

CONFIG_DIR = Path(__file__).parent.parent / "research_agent" / "config"
CONFIG_FILE = CONFIG_DIR / "user_config.yaml"
PROMPT_FILE = CONFIG_DIR / "analysis_prompt.yaml"

def save_config(config: dict) -> bool:
    """Save configuration to YAML file"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"✅ Configuration saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        return False

def save_prompt_template(prompt_data: dict) -> bool:
    """Save generated prompt template to YAML file"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(PROMPT_FILE, "w", encoding="utf-8") as f:
            yaml.dump(prompt_data, f, default_flow_style=False, allow_unicode=True)
        logger.info(f"✅ Prompt template saved to {PROMPT_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error saving prompt template: {e}")
        return False

def load_config() -> dict:
    """Load configuration from YAML file"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                logger.info(f"✅ Configuration loaded from {CONFIG_FILE}")
                return config
        logger.warning(f"⚠️ Config file not found at {CONFIG_FILE}")
        return {}
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return {}

def config_exists() -> bool:
    """Check if configuration file exists"""
    return CONFIG_FILE.exists()

def get_config_path() -> Path:
    """Get the path to the config file"""
    return CONFIG_FILE

def init_config_form():
    """Display configuration form for first-time setup"""
    st.warning("⚠️ Welcome! Please initialize your research preferences.")
    
    with st.form("init_config_form"):
        st.subheader("📋 Research Configuration")
        
        # Research fields input
        st.write("**1. Research Fields of Interest**")
        fields_input = st.text_area(
            "Enter your research fields (one per line):",
            value="Artificial Intelligence\nDigital Twin\nLarge Language Models",
            height=100,
            help="e.g., Earthquake Engineering, Sustainable Building, etc."
        )
        
        # Journals/Sources input
        st.write("**2. Preferred Journals & Sources**")
        journals_input = st.text_area(
            "Enter preferred journals (one per line):",
            value="Procedia Computer Science\nNeural Networks",
            height=100,
            help="Currently supported sources: arXiv, ScienceDirect"
        )
        
        # Data sources selection
        st.write("**3. Data Sources**")
        selected_sources = st.multiselect(
            "Select platforms to monitor:",
            ["arxiv", "sciencedirect", "asce"],
            default=["arxiv", "sciencedirect"],
            help="Which platforms should the agent crawl for papers?"
        )
        
        # Update frequency
        st.write("**4. Update Frequency**")
        update_freq = st.selectbox(
            "How often should the system update?",
            ["Every 6 hours", "Every 12 hours", "Every 24 hours", "Weekly"]
        )
        
        submitted = st.form_submit_button("💾 Save Configuration & Initialize", use_container_width=True)
        
        if submitted:
            # Validate inputs
            fields = [f.strip() for f in fields_input.split("\n") if f.strip()]
            journals = [j.strip() for j in journals_input.split("\n") if j.strip()]
            
            if not fields or not journals:
                st.error("❌ Please fill in both research fields and journals!")
                return
            
            # Create configuration dictionary
            config = {
                "fields": fields,
                "journals": journals,
                "sources": selected_sources,
                "update_frequency": update_freq
            }
            
            # Save configuration to file
            if save_config(config):
                st.session_state.user_config = config
                st.success("✅ Configuration saved!")
                st.info("📁 Config saved to: `src/research_agent/config/user_config.yaml`")

                # Generate analysis prompt template
                prompt_agent = PromptAgent()
                st.info("🤖 Generating professional analysis prompt template...")
                with st.spinner("⏳ This may take a moment..."):
                    prompt_template = prompt_agent.generate_prompt(fields)
                if prompt_template:
                    # Save prompt template to file
                    prompt_data = {
                        "based_on_fields": fields,
                        "template": prompt_template
                    }
                    if save_prompt_template(prompt_data):
                        st.success("✅ Analysis prompt template generated and saved!")
                        st.info("📁 Prompt saved to: `src/research_agent/config/analysis_prompt.yaml`")
                        
                        with st.expander("📋 View Generated Prompt Template"):
                            st.markdown(prompt_template)
                        
                        st.info("Next step: Execute `python main_demo.py` to crawl and populate the database.")
                        st.stop()
                    else:
                        st.error("❌ Failed to save the prompt template. Please try again.")

                st.info("Next step: Execute `python main_demo.py` to crawl and populate the database.")
                st.stop()