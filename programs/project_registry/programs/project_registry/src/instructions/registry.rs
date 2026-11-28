use anchor_lang::prelude::*;

use crate::{
    constants::*,
    error::RegistryError,
    instructions::project::{validate_hash, validate_uri},
    state::{CriteriaTemplate, Registry, Reviewer},
};

#[derive(Accounts)]
pub struct InitializeRegistry<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(
        init,
        payer = admin,
        space = 8 + Registry::INIT_SPACE,
        seeds = [REGISTRY_SEED],
        bump
    )]
    pub registry: Account<'info, Registry>,
    pub system_program: Program<'info, System>,
}

pub fn initialize_registry(ctx: Context<InitializeRegistry>) -> Result<()> {
    let registry = &mut ctx.accounts.registry;
    registry.admin = ctx.accounts.admin.key();
    registry.pending_admin = None;
    registry.reviewer_count = 0;
    registry.schema_version = SCHEMA_VERSION;
    registry.bump = ctx.bumps.registry;
    Ok(())
}

#[derive(Accounts)]
#[instruction(wallet: Pubkey)]
pub struct AddReviewer<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(
        mut,
        seeds = [REGISTRY_SEED],
        bump = registry.bump,
        has_one = admin @ RegistryError::UnauthorizedAdmin
    )]
    pub registry: Account<'info, Registry>,
    #[account(
        init,
        payer = admin,
        space = 8 + Reviewer::INIT_SPACE,
        seeds = [REVIEWER_SEED, registry.key().as_ref(), wallet.as_ref()],
        bump
    )]
    pub reviewer: Account<'info, Reviewer>,
    pub system_program: Program<'info, System>,
}

pub fn add_reviewer(ctx: Context<AddReviewer>, wallet: Pubkey) -> Result<()> {
    require_keys_neq!(wallet, Pubkey::default(), RegistryError::ReviewerMismatch);
    require!(
        ctx.accounts.registry.schema_version == SCHEMA_VERSION,
        RegistryError::SchemaMismatch
    );

    let reviewer = &mut ctx.accounts.reviewer;
    reviewer.wallet = wallet;
    reviewer.active = true;
    reviewer.added_at = Clock::get()?.unix_timestamp;
    reviewer.bump = ctx.bumps.reviewer;

    let registry = &mut ctx.accounts.registry;
    registry.reviewer_count = registry
        .reviewer_count
        .checked_add(1)
        .ok_or(RegistryError::RoundOverflow)?;
    Ok(())
}


#[derive(Accounts)]
#[instruction(template_id: [u8; 16])]
pub struct PublishCriteriaTemplate<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(
        seeds = [REGISTRY_SEED],
        bump = registry.bump,
        has_one = admin @ RegistryError::UnauthorizedAdmin
    )]
    pub registry: Account<'info, Registry>,
    #[account(
        init,
        payer = admin,
        space = 8 + CriteriaTemplate::INIT_SPACE,
        seeds = [CRITERIA_SEED, template_id.as_ref()],
        bump
    )]
    pub criteria_template: Account<'info, CriteriaTemplate>,
    pub system_program: Program<'info, System>,
}

pub fn publish_criteria_template(
    ctx: Context<PublishCriteriaTemplate>,
    template_id: [u8; 16],
    version: u16,
    criteria_hash: [u8; 32],
    criteria_uri: String,
) -> Result<()> {
    require!(template_id != [0u8; 16], RegistryError::InvalidCriteria);
    require!(version >= 1, RegistryError::InvalidCriteria);
    validate_hash(&criteria_hash)?;
    validate_uri(&criteria_uri)?;

    let template = &mut ctx.accounts.criteria_template;
    template.template_id = template_id;
    template.version = version;
    template.criteria_hash = criteria_hash;
    template.criteria_uri = criteria_uri;
    template.published_by = ctx.accounts.admin.key();
    template.active = true;
    template.created_at = Clock::get()?.unix_timestamp;
    template.bump = ctx.bumps.criteria_template;
    Ok(())
}

#[derive(Accounts)]
#[instruction(wallet: Pubkey)]
pub struct DeactivateReviewer<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(
        seeds = [REGISTRY_SEED],
        bump = registry.bump,
        has_one = admin @ RegistryError::UnauthorizedAdmin
    )]
    pub registry: Account<'info, Registry>,
    #[account(
        mut,
        seeds = [REVIEWER_SEED, registry.key().as_ref(), wallet.as_ref()],
        bump = reviewer.bump
    )]
    pub reviewer: Account<'info, Reviewer>,
}

pub fn deactivate_reviewer(ctx: Context<DeactivateReviewer>, wallet: Pubkey) -> Result<()> {
    let reviewer = &mut ctx.accounts.reviewer;
    require_keys_eq!(reviewer.wallet, wallet, RegistryError::ReviewerMismatch);
    require!(reviewer.active, RegistryError::ReviewerAlreadyInactive);
    reviewer.active = false;
    Ok(())
}


#[derive(Accounts)]
pub struct ProposeRegistryAdmin<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(
        mut,
        seeds = [REGISTRY_SEED],
        bump = registry.bump,
        has_one = admin @ RegistryError::UnauthorizedAdmin
    )]
    pub registry: Account<'info, Registry>,
}

pub fn propose_registry_admin(ctx: Context<ProposeRegistryAdmin>, new_admin: Pubkey) -> Result<()> {
    require_keys_neq!(new_admin, Pubkey::default(), RegistryError::InvalidIdentifier);
    require_keys_neq!(
        new_admin,
        ctx.accounts.registry.admin,
        RegistryError::InvalidIdentifier
    );
    ctx.accounts.registry.pending_admin = Some(new_admin);
    Ok(())
}

#[derive(Accounts)]
pub struct AcceptRegistryAdmin<'info> {
    pub pending_admin: Signer<'info>,
    #[account(
        mut,
        seeds = [REGISTRY_SEED],
        bump = registry.bump
    )]
    pub registry: Account<'info, Registry>,
}

pub fn accept_registry_admin(ctx: Context<AcceptRegistryAdmin>) -> Result<()> {
    let signer = ctx.accounts.pending_admin.key();
    let registry = &mut ctx.accounts.registry;
    require!(
        registry.pending_admin == Some(signer),
        RegistryError::NoPendingAdmin
    );
    registry.admin = signer;
    registry.pending_admin = None;
    Ok(())
}
