# discord.js scan skill

## SDK packages
- npm: `discord.js` (JavaScript — primary)
- rubygems: `discordrb` (Ruby)

## Import patterns

### JavaScript / TypeScript
```javascript
import { Client, GatewayIntentBits, Events } from 'discord.js';  // v14+
const { Client, Intents } = require('discord.js');                // v13 legacy
const { Client } = require('discord.js');                         // v12 and below
```

Client construction:
```javascript
// v14+ (current)
const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages] });

// v13 (legacy)
const client = new Client({ intents: [Intents.FLAGS.GUILDS, Intents.FLAGS.GUILD_MESSAGES] });
```

## Call sites to look for

### v14 canonical
- `new Client({ intents: [GatewayIntentBits.Guilds, ...] })` — client construction
- `client.on(Events.MessageCreate, (message) => ...)` — event listener
- `client.on(Events.InteractionCreate, (interaction) => ...)` — slash command handling
- `interaction.reply({ content, ephemeral })` — reply to interaction
- `interaction.deferReply()`, `interaction.editReply()` — deferred replies
- `new SlashCommandBuilder().setName().setDescription()` — command builder
- `new EmbedBuilder().setTitle().setDescription().addFields()` — embed builder

### v13 patterns (flag these)
- `new Client({ intents: [Intents.FLAGS.GUILDS] })` — `Intents.FLAGS.*` → `GatewayIntentBits.*`
- `client.on('message', (message) => ...)` — replaced by `Events.MessageCreate`
- `new MessageEmbed()` → `new EmbedBuilder()` in v14
- `new MessageActionRow()` → `new ActionRowBuilder()` in v14
- `new MessageButton()` → `new ButtonBuilder()` in v14

### v12 and below (flag these)
- `client.on('message', ...)` — no intents system
- `message.channel.send(...)` — unchanged but context differs

## v13 → v14 key breaking changes
- `Intents.FLAGS.*` removed → `GatewayIntentBits.*` (renamed enum)
- `MessageEmbed` → `EmbedBuilder`
- `MessageActionRow` → `ActionRowBuilder`
- `MessageButton` → `ButtonBuilder`
- `MessageSelectMenu` → `SelectMenuBuilder`
- `MessageAttachment` → `AttachmentBuilder`
- String event names (e.g., `'interactionCreate'`) → `Events.InteractionCreate` enum
- `client.on('ready', ...)` → `client.once(Events.ClientReady, ...)`
- ApplicationCommandType imported from `discord.js` directly (changed module path)

## v12 → v13 key breaking changes
- Discord.js v13 requires Node.js 16.6+
- Slash commands (ApplicationCommand) introduced — major new API
- Intents system introduced (required `intents` in Client constructor)
- `Message.guild` can now be null for DMs

## Where to look first
1. `grep("discord.js", "package.json")` — package presence
2. `grep("new Client\b", "")` — client constructor
3. `grep("Intents.FLAGS", "")` — detect legacy v13 intents
4. `grep("MessageEmbed\|MessageButton\|MessageActionRow", "")` — detect v13 builders
5. Common locations: `src/index.ts`, `bot.ts`, `src/bot/`, `commands/`

## Anchors (fallback signals)
- Environment variables: `DISCORD_TOKEN`, `DISCORD_BOT_TOKEN`
- `client.login(token)` call

## Common wrapper patterns
- `src/client.ts` — extended Client class
- `src/commands/` — command handlers
- `src/events/` — event handlers

## Feeds
- npm: `discord.js` package, dist-tag `latest`
- github releases: `discordjs/discord.js`
- openapi: `https://raw.githubusercontent.com/discord/discord-api-spec/main/specs/openapi.json`

## What "breaking" means for discord.js
- Builder class renames (v13→v14 was the largest: MessageEmbed→EmbedBuilder, etc.)
- Intents enum renames
- Event string → Events enum migration
- Node.js minimum version bumps
- Gateway intent changes when Discord adds required intents
