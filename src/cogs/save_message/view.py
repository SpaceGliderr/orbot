import discord


class SaveMessageEmbed(discord.Embed):
    def __init__(self, message: discord.Message, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_author(
            name=f"{message.author.name}#{message.author.discriminator}",
            icon_url=message.author.avatar.url if message.author.avatar else None,
        )

        self.add_field(name="Message Content", value=f"{message.content}", inline=False)
        self.add_field(name="Message Link", value=f"[View Message]({message.jump_url})", inline=False)

        self.set_footer(
            text=f"{message.guild.name} | #{message.channel.name}",
            icon_url=message.guild.icon.url if message.guild.icon else None,
        )
