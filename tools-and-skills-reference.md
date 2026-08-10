# Haitun's Tools & Skills Reference 🐬

> Generated: 2026-07-28

---

## 🛠️ TOOLS (168 callable tools)

### File & Shell
| Tool | What it does |
|------|-------------|
| `read` | Read file contents with line offset/limit |
| `write` | Create or overwrite a file |
| `edit` | Precise string replacement in a file |
| `list_dir` | List directory contents |
| `find_files` | Recursively find files by glob pattern |
| `search_content` | Search file contents by regex/literal |
| `bash` | Execute shell commands |
| `powershell` | Execute PowerShell commands |
| `background_start` | Start a detached background shell process |
| `background_stop` | Stop a background process |
| `background_list` | List registered background processes |

### Document Creation
| Tool | What it does |
|------|-------------|
| `write_excel` | Create real .xlsx spreadsheets |
| `write_word` | Create real .docx reports with structured blocks |
| `read_pdf` | Read PDFs (digital text layer + OCR fallback for scans) |

### Web & Browser (Playwright)
| Tool | What it does |
|------|-------------|
| `browser_navigate` | Navigate to a URL |
| `browser_snapshot` | Capture accessibility snapshot of current page |
| `browser_click` | Click an element |
| `browser_type` | Type text into editable elements |
| `browser_fill_form` | Fill multiple form fields |
| `browser_select_option` | Select dropdown options |
| `browser_hover` | Hover over an element |
| `browser_press_key` | Press a keyboard key |
| `browser_take_screenshot` | Take a screenshot |
| `browser_evaluate` | Run JavaScript on the page |
| `browser_find` | Search page snapshot for text/regex |
| `browser_wait_for` | Wait for text/time |
| `browser_tabs` | List/create/close/select tabs |
| `browser_close` | Close the page |
| `browser_navigate_back` | Go back in history |
| `browser_drag` | Drag and drop between elements |
| `browser_drop` | Drop files/data onto an element |
| `browser_file_upload` | Upload files |
| `browser_handle_dialog` | Accept/reject browser dialogs |
| `browser_mouse_click_xy` | Click at pixel coordinates |
| `browser_mouse_move_xy` | Move mouse to coordinates |
| `browser_mouse_drag_xy` | Drag mouse between coordinates |
| `browser_mouse_wheel` | Scroll the mouse wheel |
| `browser_mouse_down` / `browser_mouse_up` | Mouse press/release |
| `browser_highlight` / `browser_hide_highlight` | Highlight elements on page |
| `browser_console_messages` | Read console logs |
| `browser_network_requests` | List network requests |
| `browser_network_request` | Get full request/response details |
| `browser_resize` | Resize the browser window |
| `browser_resume` | Resume script execution (debugging) |
| `browser_run_code_unsafe` | Run arbitrary Playwright code |
| `browser_start_tracing` / `browser_stop_tracing` | Trace recording |
| `browser_start_video` / `browser_stop_video` | Video recording |
| `browser_video_chapter` | Add chapter marker to video |
| `browser_video_show_actions` / `browser_video_hide_actions` | Action annotations |
| `browser_annotate` | Open annotation dashboard |
| `browser_cdp` | Raw Chrome DevTools Protocol commands |

### Excalidraw Canvas (Live Drawing)
| Tool | What it does |
|------|-------------|
| `canvas_create_element` | Create one element (shape/text/arrow) |
| `canvas_batch_create_elements` | Create multiple elements at once |
| `canvas_update_element` | Modify an existing element |
| `canvas_delete_element` | Delete an element |
| `canvas_get_element` | Get element by ID |
| `canvas_describe_scene` | Get AI-readable scene description |
| `canvas_get_canvas_screenshot` | Screenshot the canvas |
| `canvas_create_from_mermaid` | Convert Mermaid diagram to Excalidraw |
| `canvas_export_scene` | Export to .excalidraw JSON file |
| `canvas_export_to_image` | Export to PNG/SVG |
| `canvas_export_to_excalidraw_url` | Get shareable excalidraw.com URL |
| `canvas_import_scene` | Import from .excalidraw JSON |
| `canvas_clear_canvas` | Clear all elements |
| `canvas_snapshot_scene` / `canvas_restore_snapshot` | Save/restore named snapshots |
| `canvas_align_elements` | Align to position |
| `canvas_distribute_elements` | Evenly distribute |
| `canvas_group_elements` / `canvas_ungroup_elements` | Group/ungroup |
| `canvas_duplicate_elements` | Duplicate with offset |
| `canvas_lock_elements` / `canvas_unlock_elements` | Lock/unlock elements |
| `canvas_set_viewport` | Control zoom/scroll/fit |
| `canvas_query_elements` | Query with filters/bbox |
| `canvas_get_resource` / `canvas_read_diagram_guide` | Resources |

### Feishu (Lark) Integration
#### Messages & Chat
| Tool | What it does |
|------|-------------|
| `feishu_message_send` | Send text message to chat or user |
| `feishu_message_send_card` | Send interactive card (buttons/forms) |
| `feishu_message_reply` | Reply in thread |
| `feishu_message_list` | List messages in a chat/thread |
| `feishu_image_get` | Download image from a message |
| `feishu_thread_read` | Read a topic thread |
| `feishu_topic_start` | Start a topic in a group |
| `feishu_chat_find` | Find groups by name |
| `feishu_chat_find_member` | Resolve member open_id by name |
| `feishu_chat_list_members` | List all group members |
| `feishu_chat_create` | Create new group chat |

#### Docs
| Tool | What it does |
|------|-------------|
| `feishu_doc_read` | Read docx/doc/sheet content |
| `feishu_doc_create` | Create empty document |
| `feishu_doc_append_content` | Append headings/paragraphs |
| `feishu_doc_append_table` | Append native table to doc |
| `feishu_doc_append_flowchart` | Append flowchart (single-column table) |
| `feishu_doc_append_swimlane` | Append swimlane diagram (as table) |
| `feishu_docs_search` | Search documents by keyword |

#### Spreadsheets
| Tool | What it does |
|------|-------------|
| `feishu_sheet_tabs` | List worksheets |
| `feishu_sheet_read` | Read a range of cells |
| `feishu_sheet_write` | Write values/formulas to range |
| `feishu_sheet_append` | Append rows after last used row |
| `feishu_sheet_format` | Apply cell styles |

#### Charts (22 types)
| Tool | What it does |
|------|-------------|
| `feishu_chart_pie` | Pie chart |
| `feishu_chart_donut` | Donut chart |
| `feishu_chart_funnel` | Funnel chart |
| `feishu_chart_line` | Line chart |
| `feishu_chart_area` | Area chart |
| `feishu_chart_stacked_area` | Stacked area |
| `feishu_chart_column` | Column chart |
| `feishu_chart_bar` | Horizontal bar chart |
| `feishu_chart_grouped_column` | Grouped/clustered column |
| `feishu_chart_stacked_column` | Stacked column |
| `feishu_chart_waterfall` | Waterfall bridge chart |
| `feishu_chart_histogram` | Distribution histogram |
| `feishu_chart_box` | Box plot |
| `feishu_chart_scatter` | Scatter plot |
| `feishu_chart_bubble` | Bubble chart (3 variables) |
| `feishu_chart_heatmap` | 2D intensity heatmap |
| `feishu_chart_radar` | Radar/spider chart |
| `feishu_chart_pareto` | Pareto 80/20 chart |
| `feishu_chart_combo` | Bar + line combo |
| `feishu_chart_gantt` | Gantt chart |
| `feishu_chart_progress` | Progress/attainment bars |

#### Wiki (Knowledge Base)
| Tool | What it does |
|------|-------------|
| `feishu_wiki_list_spaces` | List accessible knowledge bases |
| `feishu_wiki_list_nodes` | Browse pages in a space |
| `feishu_wiki_get_node` | Resolve node token → obj_token |
| `feishu_wiki_create_doc` | Create doc node in wiki |
| `feishu_wiki_create_doc_with_content` | Create doc + write body in one call |
| `feishu_wiki_create_space` | Create new wiki space |

#### Drive & Permissions
| Tool | What it does |
|------|-------------|
| `feishu_drive_upload` | Upload file to Drive |
| `feishu_drive_delete_file` | Delete to recycle bin |
| `feishu_drive_add_comment` | Add document comment |
| `feishu_drive_list_comments` | List comments |
| `feishu_drive_list_comment_replies` | List comment replies |
| `feishu_drive_reply_comment` | Reply to comment thread |
| `feishu_file_download` | Download file/attachment |
| `feishu_permission_add_member` | Grant file access |
| `feishu_permission_remove_member` | Revoke file access |
| `feishu_permission_list_members` | List file permissions |

#### Approval & Attendance
| Tool | What it does |
|------|-------------|
| `feishu_approval_get_definition` | Read approval form template |
| `feishu_approval_create` | Submit approval application |
| `feishu_approval_get` | Read instance (form + status + attachments) |
| `feishu_approval_decide` | Approve/reject a task |
| `feishu_approval_list_instances` | List instances in time window |
| `feishu_approval_list_tasks` | List user's pending/done tasks |
| `feishu_approval_subscribe` | Subscribe to approval status changes |
| `feishu_approval_unsubscribe` | Unsubscribe from changes |
| `feishu_attendance_query` | Query clock-in/out results |
| `feishu_attendance_groups` | List attendance groups |
| `feishu_attendance_group_config` | Get group config |
| `feishu_attendance_shifts` | List shifts |
| `feishu_attendance_shift_config` | Get shift config |

#### Calendar, Tasks, Contacts, E-learning
| Tool | What it does |
|------|-------------|
| `feishu_calendar_create_event` | Create shared meeting |
| `feishu_calendar_create_per_person` | Create per-person events |
| `feishu_calendar_list_events` | Read schedule |
| `feishu_task_create` | Create task |
| `feishu_task_get` | Get task details |
| `feishu_task_list` | List bot's own tasks |
| `feishu_task_update` | Update task |
| `feishu_task_complete` | Complete/reopen task |
| `feishu_department_members` | List department members |
| `feishu_contact_search` | Search org-wide by name |
| `feishu_user_get` | Get contact details (phone/email) |
| `feishu_elearning_list_registrations` | List learning records |
| `feishu_auth_start` / `feishu_auth_complete` | User OAuth flow |
| `feishu_bitable_list_tables` | List data tables in base |
| `feishu_bitable_list_fields` | List table columns |
| `feishu_bitable_list_records` | List records |
| `feishu_bitable_create_record` | Create record |
| `feishu_bitable_delete_records` | Delete records |
| `feishu_bitable_clear_table` | Delete all records |
| `feishu_bitable_delete_fields` | Delete fields |
| `feishu_bitable_create_role` | Create custom role |
| `feishu_bitable_list_roles` | List roles |
| `feishu_bitable_add_role_member` | Assign user to role |

### Discord
| Tool | What it does |
|------|-------------|
| `list_guilds` | List servers bot is in |
| `send_message` | Send text to channel |
| `fetch_messages` | Read recent messages |
| `react` | Add reaction emoji |
| `fetch_channel` | Get channel metadata |
| `search_members` | Search members by name |
| `list_channels` | List server channels |
| `list_roles` | List server roles |
| `create_channel` | Create channel |
| `edit_channel` | Edit channel name/topic/parent |
| `delete_channel` | Delete channel |
| `kick_member` | Kick member |
| `ban_member` | Ban user |
| `unban_member` | Lift ban |
| `timeout_member` | Time out (mute) |
| `grant_role` | Grant role to member |
| `revoke_role` | Revoke role from member |

### Knowledge & Memory
| Tool | What it does |
|------|-------------|
| `wiki_write` | Create/update LLM wiki page |
| `wiki_read` | Read wiki page |
| `wiki_search` | Full-text search wiki |
| `wiki_list` | List all wiki pages |
| `wiki_links` | Show page link graph (outgoing/backlinks/broken) |
| `wiki_delete` | Delete wiki page |
| `memory_add` | Store durable fact in Fusion Memory |
| `memory_search` | Search Fusion Memory |
| `memory_answer_context` | Get query-grounded memory context |
| `memory_health` | Check Fusion Memory connectivity |

### Search & Web
| Tool | What it does |
|------|-------------|
| `serper_google_search` | Google web search |
| `serper_google_search_news` | Google News search |
| `serper_google_search_images` | Google Image search |
| `serper_google_search_videos` | Google Video search |
| `serper_google_search_maps` | Google Maps search |
| `serper_google_search_shopping` | Google Shopping search |
| `serper_google_search_scholar` | Google Scholar search |
| `serper_google_search_patents` | Google Patents search |
| `serper_google_search_places` | Google Places search |
| `serper_google_search_reviews` | Google Reviews search |
| `serper_google_search_lens` | Google Lens search |
| `serper_google_search_autocomplete` | Google Autocomplete |
| `serper_webpage_scrape` | Scrape a webpage |
| `x_search` | Search recent X/Twitter posts |
| `fetch` | Fetch URL as markdown |
| `tool_search` | Search tool catalog by keyword |
| `tool_search_code` | Search tool source code |
| `tool_describe` | Get full tool definition & docs |
| `inspect_codebase` | Codebase LOC/language breakdown |

### Image & Audio
| Tool | What it does |
|------|-------------|
| `describe_image` | Describe/answer about an image |
| `generate_image` | Generate image from text description |
| `speech_to_text` | Transcribe audio (iFLYTEK) |
| `text_to_speech` | Synthesize speech to MP3 |

### Session & Agent Management
| Tool | What it does |
|------|-------------|
| `todo` | Manage in-session task list |
| `sessions_list` | List workspace sessions |
| `sessions_history` | Read session conversation history |
| `sessions_export` | Export session transcript |
| `sessions_create` | Create new Gateway session |
| `sessions_handoff` | Transfer work to another session |
| `session_status` | Inspect session runtime info |
| `session_keyword_search` | Search session histories by keyword |
| `session_task_search` | List sessions by task category |
| `skill_manage` | Create/list/view/patch skills |
| `flow_manage` | Create/patch/list/promote flows |
| `flow_run` | Run a Fusion Flow (.flow.ts) |
| `schedule_manage` | Create/list/view/patch/delete scheduled tasks |
| `subagent_plan` | Plan subagent spawn |
| `subagent_wait` | Wait for subagent socket |
| `subagent_chat` | Send message to subagent |
| `goal_set` | Create/update high-level goal |
| `goal_progress` | Record progress on a goal |
| `goal_get` | Read goal state |
| `goal_list` | List all goals with status rollup |
| `goal_delete` | Delete a goal |
| `clarify` | Ask user a blocking question |
| `macOS` / `computer_use` | Drive macOS desktop background |

---

## 📚 SKILLS (100+ reusable instruction files)

### Agent Skills (loaded by task matching)
| Skill | Category | What it guides |
|-------|----------|---------------|
| `_universal` | general | Always-loaded working discipline |
| `psi-agent-help` | agent | Workspace onboarding & help |
| `session-management` | agent | Discover, export, hand off sessions |
| `task-planning` | agent | Decompose work with todo lists |
| `task-self-check` | agent | Verify before final reply |
| `subagent-orchestration` | agent | Spawn child agents for isolation/parallelism |
| `plan` | agent | Plan mode: decompose before doing |
| `ontology` | agent | Typed knowledge graph over LLM wiki |
| `taskflow-inbox-triage` | agent | Turn inbox items into prioritized tasks |
| `user-preferences-and-language` | agent | Capture user preferences for future sessions |

### Coding
| Skill | What it guides |
|-------|---------------|
| `code-review-checklist` | PR review checklist for Python |
| `codebase-inspection` | LOC/language breakdown |
| `git-workflow` | Safe git branching/committing/PRs |
| `github-repo-management` | Clone/create/fork repos |
| `llm-wiki` | Build cross-linked knowledge base |
| `node-inspect-debugger` | Debug Node.js programs |
| `python-async-basics` | Python asyncio fundamentals |
| `python-debugpy` | Remote DAP debug for Python |
| `python-static-analysis` | Static analysis & type checking |
| `test-driven-development` | TDD red-green-refactor |
| `tmux` | Persistent terminal sessions |
| `huggingface-hub` | Search/download/upload HF models |
| `spike` | Time-boxed technical experiment |
| `simplify-code` | Fan-out 3 subagents to cleanup code |
| `dogfood` | Exploratory QA on live web apps |

### Autonomous AI Agents
| Skill | What it guides |
|-------|---------------|
| `claude-code` | Delegate coding to Claude Code CLI |
| `codex` | Delegate coding to OpenAI Codex CLI |
| `opencode` | Delegate coding to OpenCode CLI |
| `hermes-agent` | Configure/run Hermes agent framework |

### Creative
| Skill | What it guides |
|-------|---------------|
| `architecture-diagram` | Dark SVG architecture diagrams as HTML |
| `excalidraw` | Generate hand-drawn style diagrams (.excalidraw) |
| `pretext` | Creative kinetic typography browser demos |
| `comfyui` | Local ComfyUI image/video generation |
| `touchdesigner-mcp` | Control TouchDesigner via MCP |

### Research
| Skill | What it guides |
|-------|---------------|
| `arxiv` | Search arXiv papers |
| `weather` | Current weather & forecasts (Open-Meteo) |
| `maps` | Geocoding, POIs, routing (OSM/Nominatim/OSRM) |
| `goplaces` | Google Places API (business search/details) |
| `youtube-content` | Extract transcript → summary/thread/blog |
| `blogwatcher` | Monitor RSS/Atom feeds |
| `ocr-and-documents` | PDF text extraction + OCR |
| `research-paper-writing` | ML paper writing for NeurIPS/ICML/ICLR |

### Productivity
| Skill | What it guides |
|-------|---------------|
| `taskflow` | Durable cross-session task/project board |
| `trello` | Manage Trello boards via API |
| `airtable` | Read/write Airtable bases |
| `feishu-self-service-agent` | File approvals for employees |
| `feishu-leave-audit-board` | Auto-audit leave approvals |
| `feishu-reimbursement-archive` | Archive reimbursement docs |
| `feishu-reimbursement-audit-report` | Auto-audit reimbursements |
| `feishu-attendance-payroll` | Attendance → payroll report |
| `feishu-blocker-routing` | Find who to contact when stuck |
| `feishu-todo-board-sync` | Sync personal ToDoList to team board |
| `feishu-work-handoff-delegate` | Work sync & handoff delegation |
| `contract-ledger` | Maintain contract ledger in bitable |
| `contract-review-sop` | Legal contract review SOP |
| `contract-legal-governance` | Contract autonomy rulebook |
| `feishu-schedule-message` | Feishu timed reminders |

### Knowledge Base
| Skill | What it guides |
|-------|---------------|
| `admin-finance-governance` | Admin/finance tiered autonomy rules |
| `feishu-admin-finance-assistant` | Policy Q&A from Feishu docs |
| `feishu-mentor-feedback` | Collect/summarize mentor feedback |
| `contract-law-source` | Legal basis for contract findings |
| `notion` | Read/write Notion pages & databases |
| `obsidian` | Read/write Obsidian vault notes |

### Output
| Skill | What it guides |
|-------|---------------|
| `document-report-authoring` | Word/PPT/Excel report files |
| `powerpoint` | Create/edit .pptx decks |
| `nano-pdf` | Edit text inside existing PDFs |
| `structured-output-tables` | Table formatting rules |
| `feishu-charts` | 22 chart types for Feishu docs |

### Media
| Skill | What it guides |
|-------|---------------|
| `image-generation` | Text-to-image via generate_image |
| `image-understanding` | Describe image contents |
| `speech-to-text` | iFLYTEK audio transcription |
| `text-to-speech` | iFLYTEK MP3 synthesis |
| `gif-search` | Search/download GIFs |

### Social
| Skill | What it guides |
|-------|---------------|
| `xurl` | Post/search/DM on X/Twitter |

### Email
| Skill | What it guides |
|-------|---------------|
| `himalaya` | IMAP/SMTP email management |

### Google
| Skill | What it guides |
|-------|---------------|
| `gog` | Gmail/Calendar/Drive/Docs/Sheets via CLI |

### Apple (macOS)
| Skill | What it guides |
|-------|---------------|
| `macos-computer-use` | Drive native Mac apps in background |
| `apple-notes` | Manage Apple Notes |
| `apple-imessage` | Send/receive iMessages & SMS |

### GitHub
| Skill | What it guides |
|-------|---------------|
| `github-auth` | GitHub authentication setup |
| `github-code-review` | Review PRs with gh CLI |
| `github-issues` | Manage GitHub issues |

### Flow / Fusion
| Skill | What it guides |
|-------|---------------|
| `flow` | Author `.flow.ts` multi-agent workflows |
| `fusion-memory-setup` | Configure Fusion Memory MCP |

### Haibao (Business Data)
| Skill | What it guides |
|-------|---------------|
| `haibao` | Query real business data via Haibao ChatBI |

### General (specialized domains)
| Skill | What it guides |
|-------|---------------|
| `binary-reverse-engineering` | Reverse binaries, extract secrets |
| `cryptanalysis` | Attack ciphers, recover keys |
| `digital-circuit-construction` | Gate-level circuit synthesis |
| `compressor-from-decompressor` | Write encoder matching given decoder |
| `host-conformant-offline-reconstruct` | Build artifact for fixed host loader |
| `interpreter-in-target-language` | Metacircular evaluators |
| `workload-driven-emulator-fidelity` | Write CPU/ISA emulator |
| `ml-inference-from-scratch` | Model inference from raw weights |
| `distributed-training-parallelism` | Parallelize training across ranks |
| `model-extraction-attack` | Black-box NN parameter extraction |
| `text-classifier-training` | Train classifier to pass threshold |
| `image-segmentation` | SAM-based object segmentation |
| `video-motion-analysis` | Find event frame in video |
| `physics-sim-tuning` | Speed up MuJoCo simulations |
| `scientific-curve-fitting` | Fit peaks to spectroscopy data |
| `statistical-sampling-algorithms` | MCMC, Gibbs, ARS samplers |
| `database-query-optimization` | Optimize slow SQL queries |
| `data-text-processing` | ETL/wrangling/document extraction |
| `regex-codegen` | Generate regex for text extraction |
| `html-sanitization` | Build XSS filter |
| `primer-design-cloning` | PCR primer design for molecular cloning |
| `redcode-corewars` | Write Core War warriors |
| `leaderboard-snapshot-query` | Point-in-time leaderboard rankings |
| `legacy-emulation-setup` | Boot old OS/app under QEMU/DOSBox |
| `legacy-ml-framework-build` | Build & run legacy ML framework example |
| `c-systems-build` | Fix C/C++/Rust/OCaml builds |
| `sysadmin-infra` | Servers, VMs, TLS, nginx |
| `async-concurrency-python` | Correct Python asyncio patterns |
| `oracle-checked-substrate-synthesis` | Regex/substitution computation |
| `media-graphics` | Ray tracing, rendering, physics |
| `example-skill` | SKILL.md format demo |
| `haibao` | Business data queries |
