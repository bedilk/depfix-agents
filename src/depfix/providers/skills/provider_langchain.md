# LangChain scan skill

## SDK packages
- npm: `@langchain/core`, `@langchain/openai`, `@langchain/anthropic`, `langchain`
- pypi: `langchain`, `langchain-core`, `langchain-openai`, `langchain-anthropic`, `langchain-community`

## Import patterns

### JavaScript / TypeScript
```javascript
import { ChatOpenAI } from '@langchain/openai';         // v0.1+ (split packages)
import { ChatAnthropic } from '@langchain/anthropic';
import { ChatOpenAI } from 'langchain/chat_models/openai'; // legacy pre-0.1
import { LLMChain } from 'langchain/chains';            // legacy
```

### Python
```python
# Modern (post-0.1.0 split, Dec 2023)
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Legacy (pre-0.1.0)
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain, ConversationChain
from langchain.llms import OpenAI
```

## Call sites to look for
- `new ChatOpenAI({modelName: 'gpt-4', temperature: 0})` — JS model construction
- `ChatOpenAI(model='gpt-4o')` — Python model construction
- `chain.invoke({...})` / `chain.stream({...})` — LCEL invocation
- `LLMChain({ llm, prompt })` — legacy chain (flag if seen)
- `ConversationChain(...)` — legacy, flag if seen
- `agent.run(...)` / `agent.invoke(...)` — agent invocation

## Legacy patterns (flag these — pre-0.1.0 split)
### Python
- `from langchain.chat_models import ChatOpenAI` → `from langchain_openai import ChatOpenAI`
- `from langchain.chains import LLMChain` — legacy, migrate to LCEL
- `from langchain.llms import OpenAI` → `from langchain_openai import OpenAI`
- `from langchain.callbacks import` → `from langchain_core.callbacks import`
- `LLMChain(llm=llm, prompt=prompt)` — use LCEL `prompt | llm` instead

### JavaScript
- `import { ChatOpenAI } from 'langchain/chat_models/openai'` → `from '@langchain/openai'`
- `import { LLMChain } from 'langchain/chains'` — deprecated

## v0.0.x → v0.1.x key breaking changes (Dec 2023 "split")
- Provider classes moved to separate packages (`langchain_openai`, `langchain_anthropic`, etc.)
- `langchain-community` for third-party integrations
- `langchain-core` for base classes (BaseChain, BaseChatModel, etc.)
- LCEL (`|` pipe operator) replaces LLMChain, ConversationChain
- `chain.run(input)` → `chain.invoke(input)` (invoke is the new standard)

## v0.1.x → v0.2.x / v0.3.x changes
- `AgentExecutor` still supported but LCEL agent preferred
- Memory classes (`ConversationBufferMemory`) deprecated in favor of LangGraph
- `chain.run()` method removed in v0.2 (use `invoke`)

## Where to look first
1. `grep("from langchain", "")` — any langchain import (Python)
2. `grep("langchain/\|@langchain/", "")` — JS imports
3. Look for `chains/`, `agents/`, `llm.py`, `ai.py`, `chat.py`
4. `grep("LLMChain\|ConversationChain", "")` — detect legacy chain patterns

## Anchors (fallback signals)
- `langchain` in requirements.txt / package.json is the primary signal
- `LANGCHAIN_API_KEY` env var → LangSmith tracing enabled

## Common wrapper patterns
- `lib/langchain.ts` or `utils/llm.py` — model instance export
- Chain definitions often in `chains/` directory

## Feeds
- npm: `@langchain/openai` package, dist-tag `latest`
- pypi: `langchain` project, `langchain-core`, `langchain-openai`
- github releases: `langchain-ai/langchainjs`, `langchain-ai/langchain`

## What "breaking" means for LangChain
- Provider package splits (the 0.1.0 migration was the biggest)
- Method renames: `run()` → `invoke()`
- Base class moves between `langchain` and `langchain-core`
- Memory / agent API changes across minor versions (LangChain ships breaking changes in minors)
- LCEL operator (`|`) replaces chain classes
