# GPT Arbiter Human-in-Loop
- Classify items according to your prompt and examples.  
  - e.g. [Which papers in this database are relevant to...?](https://github.com/Daniel-Chin/GPT-lit-reviewer)  
  - e.g. [Which YouTube videos in this metadatabase look like music?](https://github.com/Daniel-Chin/sync-my-youtube-playlists)  
- The GPT model outputs one token, saving costs.  
- The output token's logits represent its confidence.  
- Low-confidence decisions query the human user for labeling. Labels are added to the prompt as in-context examples.  

## More features
- Cached API responses save costs when you rerun after interruption.  
  - With cache key as the full prompt and model selection, ensuring validity.  
- Terminal ascii GUI (with `textual`):  
  - Displays in realtime the histogram of classification confidence.
    - In binary classification, one hist represents decisions+confidence. In multi classification, one hist shows the confidence and one 100% stacked bar chart shows the decisions.
  - Displays in realtime the database coverage, using different symbols to represent "unvisited", "visited with latest prompt", "visited with stale (-2) prompt", etc.
  - Displays the running cost in USD.  
  - Accepts user commands to:
    - label the current query.  
    - Set throttling.
    - Pause/resume background classification.

## Maybe todo
- Use ChatCompletion during the interactive stage and hand it off to BatchAPI for the automatic stage.
