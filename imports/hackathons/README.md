# Hackathon Platform Imports

Place `.json` or `.csv` exports from hackathon platforms in this folder.

Supported fields:

```text
id,title,organizer,platform,status,deadline,url,notes,updated_at
```

JSON can be either an array or an object containing `hackathons` or `items`.

The Hackathon Platforms connector deduplicates records by `id`. Use a stable platform application or event ID whenever possible.
