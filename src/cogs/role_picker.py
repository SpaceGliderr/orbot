from typing import List
import discord
from discord.ext import commands
from ruamel.yaml import YAML

from src.utils.config import RolePickerConfig
from src.utils.helper import dict_has_key
from src.utils.ui import Dropdown, Button, View


yaml = YAML(typ="safe")


class RolePicker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(pass_context=True)
    async def role_picker(self, ctx: commands.Context):
        rp_conf = RolePickerConfig()

        view = View()
        for category in rp_conf.role_categories:
            view.add_item(Button(label=category["label"], value=category["name"]))

        message = await ctx.send("Welcome to the bias picker, please select a role category", view=view)
        
        await view.wait()
        await message.delete()

        role_category = view.values

        roles = rp_conf.get_roles(role_category)
        role_ids = rp_conf.get_role_ids(role_category)
        user_role_ids = [role.id for role in ctx.author.roles]
        options: List[discord.SelectOption] = []

        for role in roles:
            option = discord.SelectOption(label=role["label"], value=rp_conf.get_role_id(role, role_category))

            if option.value in user_role_ids:
                option.default = True

            if dict_has_key(role, "emoji"):
                option.emoji = role["emoji"]

            options.append(option)

        view = View()
        view.add_item(Dropdown(
            min_values = 0, 
            max_values = len(options),
            options = options
        ))

        message = await ctx.send(f"Select roles!", view=view)

        await view.wait()
        await message.delete()
        
        selected_role_ids = [int(role_id) for role_id in view.values]
        common_current_role_ids = list(set(user_role_ids).intersection(set(role_ids)))
        common_selected_role_ids = list(set(selected_role_ids).intersection(set(user_role_ids)))

        role_ids_to_add = [role_id for role_id in selected_role_ids if role_id not in common_selected_role_ids]
        role_ids_to_del = [role_id for role_id in common_current_role_ids if role_id not in common_selected_role_ids]

        for role_id in role_ids_to_add:
            role = ctx.guild.get_role(int(role_id))
            await ctx.author.add_roles(role)

        for role_id in role_ids_to_del:
            role = ctx.guild.get_role(int(role_id))
            await ctx.author.remove_roles(role)


async def setup(bot):
    await bot.add_cog(RolePicker(bot))
