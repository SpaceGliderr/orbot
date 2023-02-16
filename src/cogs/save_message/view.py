import discord


class SaveMessageEmbed(discord.Embed):
    """Creates an embed that displays the contents of a saved message.

    Parameters
    ----------
        * message: :class:`discord.Message`
            - The message that was saved by the user.
    """

    def __init__(self, message: discord.Message, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_author(
            name=f"{message.author.name}#{message.author.discriminator}",
            icon_url=message.author.avatar.url if message.author.avatar else None,
        )

        message_content = ""

        if message.content != "":
            message_content += message.content

        if len(message.embeds) > 0:
            message_content += "\n\n_<Message contains embeds>_" if message_content else "_<Message contains embeds>_"

        if message_content != "":
            self.add_field(name="Message Content", value=message_content, inline=False)

        if message.attachments:
            attachment_filenames = []
            is_image_set = False

            for attachment in message.attachments:
                attachment_filenames.append(f"`{attachment.filename}`")

                if not is_image_set and attachment.content_type and attachment.content_type == "image/png":
                    self.set_image(url=attachment.url)
                    is_image_set = True

            self.add_field(name="Message Attachments", value=", ".join(attachment_filenames), inline=False)

        self.add_field(name="Message Link", value=f"[View Message]({message.jump_url})", inline=False)

        self.set_footer(
            text=f"{message.guild.name} | #{message.channel.name}",
            icon_url=message.guild.icon.url if message.guild.icon else None,
        )
