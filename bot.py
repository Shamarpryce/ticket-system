import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import json
import os

# Configure intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Initialize bot
bot = commands.Bot(command_prefix="!", intents=intents)


class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_category_id = None  # Set this to your category ID!
        self.support_role_id = 1464120540057833534  # Role that can view tickets
        self.image_url = "https://cdn.discordapp.com/attachments/1464120729346773003/1465123454557884458/Michigan.png?ex=697e8d8c&is=697d3c0c&hm=fa4508a4ea540b8ebdfc0bf682837cf60e00eefdde02b0d5b382d5f64e7ed2c8&"
        
        # Emojis
        self.check_emoji = "<:Check:1465396492029137041>"
        self.cog_emoji = "<:michigan_cog:1465146649302138932>"
        self.file_emoji = "<:michigan_file:1465147722922463373>"
        
        # Load ticket data
        self.tickets_file = "tickets.json"
        self._load_tickets()
    
    def _load_tickets(self):
        """Load ticket data from file"""
        if os.path.exists(self.tickets_file):
            with open(self.tickets_file, 'r') as f:
                self.tickets = json.load(f)
        else:
            self.tickets = {
                "counter": 0,
                "active_tickets": {},
                "ticket_history": {}
            }
    
    def _save_tickets(self):
        """Save ticket data to file"""
        with open(self.tickets_file, 'w') as f:
            json.dump(self.tickets, f, indent=4)
    
    def _get_next_ticket_number(self):
        """Get next ticket number"""
        self.tickets["counter"] += 1
        self._save_tickets()
        return self.tickets["counter"]
    
    @app_commands.command(name="ticket_setup", description="Setup the ticket system panel")
    async def ticket_setup(self, interaction: discord.Interaction):
        """Setup ticket panel"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You must be an administrator to use this command.",
                ephemeral=True
            )
            return
        
        # Create the main embed
        embed = discord.Embed(
            title="Michigan State Roleplay Support",
            description=(
                "Press the button below to open a ticket, then wait for a staff member "
                "to help you. Doesn't matter what type of support you need; make a ticket, "
                "and your problem will be solved.\n\n"
                "• **Appeal**\n"
                "• **Report**\n"
                "• **General**\n"
                "• **Management**\n"
                "• **Partners**\n\n"
                "Open a support ticket today! Don't be shy."
            ),
            color=discord.Color.from_rgb(52, 211, 153)
        )
        
        embed.set_image(url=self.image_url)
        embed.set_footer(text="Powered by Michigan State Roleplay")
        
        # Create the view with button
        view = TicketPanelView(self)
        
        await interaction.response.send_message(
            f"{self.check_emoji} Ticket panel created!",
            ephemeral=True
        )
        
        # Send the panel
        channel = interaction.channel
        await channel.send(embed=embed, view=view)
    
    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str):
        """Create a new ticket"""
        # Check if user already has an open ticket
        user_id = str(interaction.user.id)
        for ticket_id, ticket_data in self.tickets["active_tickets"].items():
            if ticket_data["user_id"] == interaction.user.id:
                await interaction.response.send_message(
                    f"❌ You already have an open ticket: <#{ticket_data['channel_id']}>",
                    ephemeral=True
                )
                return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get ticket number
        ticket_number = self._get_next_ticket_number()
        ticket_id = f"ticket-{ticket_number}"
        
        # Get category
        category = interaction.guild.get_channel(self.ticket_category_id) if self.ticket_category_id else None
        
        # Create ticket channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True
            )
        }
        
        # Add support role permissions
        support_role = interaction.guild.get_role(self.support_role_id)
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True
            )
        
        # Create channel
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{ticket_number}",
            category=category,
            overwrites=overwrites,
            topic=f"{ticket_type} ticket by {interaction.user.name} (ID: {interaction.user.id})"
        )
        
        # Save ticket data
        self.tickets["active_tickets"][ticket_id] = {
            "ticket_number": ticket_number,
            "channel_id": channel.id,
            "user_id": interaction.user.id,
            "user_name": str(interaction.user),
            "type": ticket_type,
            "created_at": datetime.now().isoformat(),
            "status": "open"
        }
        self._save_tickets()
        
        # Create welcome embed
        welcome_embed = discord.Embed(
            title=f"{self.cog_emoji} Ticket #{ticket_number} - {ticket_type}",
            description=(
                f"Welcome {interaction.user.mention}!\n\n"
                f"**Ticket Type:** {ticket_type}\n"
                f"**Created:** <t:{int(datetime.now().timestamp())}:F>\n\n"
                f"A staff member will be with you shortly. Please describe your issue in detail."
            ),
            color=discord.Color.from_rgb(52, 211, 153)
        )
        welcome_embed.set_thumbnail(url=interaction.user.display_avatar.url)
        welcome_embed.set_footer(text=f"Ticket ID: {ticket_id}")
        
        # Create control buttons
        control_view = TicketControlView(self, ticket_id)
        
        # Send welcome message
        await channel.send(
            content=f"{interaction.user.mention} {support_role.mention if support_role else ''}",
            embed=welcome_embed,
            view=control_view
        )
        
        # Confirm to user
        await interaction.followup.send(
            f"{self.check_emoji} Ticket created: {channel.mention}",
            ephemeral=True
        )
    
    async def close_ticket(self, interaction: discord.Interaction, ticket_id: str, reason: str = "No reason provided"):
        """Close a ticket"""
        if ticket_id not in self.tickets["active_tickets"]:
            await interaction.response.send_message(
                "❌ This ticket is no longer active.",
                ephemeral=True
            )
            return
        
        ticket_data = self.tickets["active_tickets"][ticket_id]
        
        # Create closing embed
        close_embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=(
                f"This ticket has been closed by {interaction.user.mention}\n\n"
                f"**Reason:** {reason}\n"
                f"**Closed at:** <t:{int(datetime.now().timestamp())}:F>\n\n"
                f"This channel will be deleted in 10 seconds."
            ),
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=close_embed)
        
        # Move to history
        ticket_data["closed_by"] = str(interaction.user)
        ticket_data["closed_at"] = datetime.now().isoformat()
        ticket_data["close_reason"] = reason
        ticket_data["status"] = "closed"
        
        self.tickets["ticket_history"][ticket_id] = ticket_data
        del self.tickets["active_tickets"][ticket_id]
        self._save_tickets()
        
        # Delete channel after delay
        import asyncio
        await asyncio.sleep(10)
        channel = interaction.channel
        await channel.delete(reason=f"Ticket closed by {interaction.user}")
    
    async def add_user_to_ticket(self, interaction: discord.Interaction, ticket_id: str, user: discord.Member):
        """Add a user to the ticket"""
        if ticket_id not in self.tickets["active_tickets"]:
            await interaction.response.send_message(
                "❌ This ticket is no longer active.",
                ephemeral=True
            )
            return
        
        channel = interaction.channel
        await channel.set_permissions(
            user,
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True
        )
        
        embed = discord.Embed(
            description=f"{self.check_emoji} {user.mention} has been added to the ticket by {interaction.user.mention}",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def remove_user_from_ticket(self, interaction: discord.Interaction, ticket_id: str, user: discord.Member):
        """Remove a user from the ticket"""
        if ticket_id not in self.tickets["active_tickets"]:
            await interaction.response.send_message(
                "❌ This ticket is no longer active.",
                ephemeral=True
            )
            return
        
        ticket_data = self.tickets["active_tickets"][ticket_id]
        
        # Don't remove ticket owner
        if user.id == ticket_data["user_id"]:
            await interaction.response.send_message(
                "❌ Cannot remove the ticket owner.",
                ephemeral=True
            )
            return
        
        channel = interaction.channel
        await channel.set_permissions(user, overwrite=None)
        
        embed = discord.Embed(
            description=f"❌ {user.mention} has been removed from the ticket by {interaction.user.mention}",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ticket_add", description="Add a user to the ticket")
    @app_commands.describe(user="The user to add to the ticket")
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        """Add user to ticket"""
        # Check if in a ticket channel
        ticket_id = None
        for tid, tdata in self.tickets["active_tickets"].items():
            if tdata["channel_id"] == interaction.channel.id:
                ticket_id = tid
                break
        
        if not ticket_id:
            await interaction.response.send_message(
                "❌ This command can only be used in a ticket channel.",
                ephemeral=True
            )
            return
        
        await self.add_user_to_ticket(interaction, ticket_id, user)
    
    @app_commands.command(name="ticket_remove", description="Remove a user from the ticket")
    @app_commands.describe(user="The user to remove from the ticket")
    async def ticket_remove(self, interaction: discord.Interaction, user: discord.Member):
        """Remove user from ticket"""
        # Check if in a ticket channel
        ticket_id = None
        for tid, tdata in self.tickets["active_tickets"].items():
            if tdata["channel_id"] == interaction.channel.id:
                ticket_id = tid
                break
        
        if not ticket_id:
            await interaction.response.send_message(
                "❌ This command can only be used in a ticket channel.",
                ephemeral=True
            )
            return
        
        await self.remove_user_from_ticket(interaction, ticket_id, user)
    
    @app_commands.command(name="ticket_close", description="Close the current ticket")
    @app_commands.describe(reason="Reason for closing the ticket")
    async def ticket_close_command(self, interaction: discord.Interaction, reason: str = "No reason provided"):
        """Close ticket command"""
        # Check if in a ticket channel
        ticket_id = None
        for tid, tdata in self.tickets["active_tickets"].items():
            if tdata["channel_id"] == interaction.channel.id:
                ticket_id = tid
                break
        
        if not ticket_id:
            await interaction.response.send_message(
                "❌ This command can only be used in a ticket channel.",
                ephemeral=True
            )
            return
        
        await self.close_ticket(interaction, ticket_id, reason)


class TicketPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(
        label="📁 Create a ticket",
        style=discord.ButtonStyle.danger,
        custom_id="create_ticket_button"
    )
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show category selection
        view = TicketCategoryView(self.cog)
        
        embed = discord.Embed(
            title="Select Ticket Category",
            description="Please select the category that best describes your issue:",
            color=discord.Color.from_rgb(52, 211, 153)
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TicketCategoryView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog
    
    @discord.ui.button(label="Appeal", style=discord.ButtonStyle.secondary, emoji="⚖️")
    async def appeal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.create_ticket(interaction, "Appeal")
    
    @discord.ui.button(label="Report", style=discord.ButtonStyle.secondary, emoji="🚨")
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.create_ticket(interaction, "Report")
    
    @discord.ui.button(label="General", style=discord.ButtonStyle.secondary, emoji="💬")
    async def general_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.create_ticket(interaction, "General")
    
    @discord.ui.button(label="Management", style=discord.ButtonStyle.secondary, emoji="👔")
    async def management_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.create_ticket(interaction, "Management")
    
    @discord.ui.button(label="Partners", style=discord.ButtonStyle.secondary, emoji="🤝")
    async def partners_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.create_ticket(interaction, "Partners")


class TicketControlView(discord.ui.View):
    def __init__(self, cog, ticket_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show confirmation with reason input
        modal = CloseTicketModal(self.cog, self.ticket_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="✋", custom_id="claim_ticket")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            description=f"{self.cog.check_emoji} {interaction.user.mention} has claimed this ticket and will assist you.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


class CloseTicketModal(discord.ui.Modal, title="Close Ticket"):
    reason = discord.ui.TextInput(
        label="Reason for closing",
        placeholder="Enter the reason for closing this ticket...",
        required=False,
        max_length=200,
        style=discord.TextStyle.paragraph
    )
    
    def __init__(self, cog, ticket_id):
        super().__init__()
        self.cog = cog
        self.ticket_id = ticket_id
    
    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value or "No reason provided"
        await self.cog.close_ticket(interaction, self.ticket_id, reason)


# Bot events
@bot.event
async def on_ready():
    print(f'{bot.user} is now online!')
    print(f'Ticket Bot Ready!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


# Main function
async def main():
    async with bot:
        # Load ticket system
        await bot.add_cog(TicketSystem(bot))
        
        # Bot token - CHANGE THIS TO YOUR TICKET BOT TOKEN
        TOKEN = "MTQxOTI3NjU1Mzg5MTg3MjgxOQ.GZ8JX8.ai6flV_exE0dat8bDpKCe7SQ0THSRs_QShQE3Y"
        
        # Start the bot
        await bot.start(TOKEN)


# Run the bot
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
