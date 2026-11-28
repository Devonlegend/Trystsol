use anchor_lang::prelude::*;

use crate::{
    constants::*,
    error::RegistryError,
    state::{LifecycleStatus, Project, Registry},
};

#[derive(Accounts)]
#[instruction(project_id: [u8; 16], metadata_hash: [u8; 32], metadata_uri: String)]
pub struct RegisterProject<'info> {
    /// The admin registers an approved project; the founder becomes the authority.
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
        space = 8 + Project::INIT_SPACE,
        seeds = [PROJECT_SEED, project_id.as_ref()],
        bump
    )]
    pub project: Account<'info, Project>,
    pub system_program: Program<'info, System>,
}

pub fn register_project(
    ctx: Context<RegisterProject>,
    project_id: [u8; 16],
    metadata_hash: [u8; 32],
    metadata_uri: String,
    founder: Pubkey,
) -> Result<()> {
    require!(project_id != [0u8; 16], RegistryError::InvalidIdentifier);
    require_keys_neq!(founder, Pubkey::default(), RegistryError::InvalidIdentifier);
    require_keys_neq!(
        founder,
        ctx.accounts.admin.key(),
        RegistryError::InvalidIdentifier
    );
    validate_uri(&metadata_uri)?;
    require!(
        ctx.accounts.registry.schema_version == SCHEMA_VERSION,
        RegistryError::SchemaMismatch
    );

    // The admin registers the project, but the founder must explicitly accept
    // authority before creating or submitting milestones.
    let project = &mut ctx.accounts.project;
    project.authority = ctx.accounts.admin.key();
    project.pending_authority = Some(founder);
    project.metadata_hash = metadata_hash;
    project.metadata_uri = metadata_uri;
    project.lifecycle_status = LifecycleStatus::Active;
    project.created_at = Clock::get()?.unix_timestamp;
    project.bump = ctx.bumps.project;
    Ok(())
}

pub fn validate_uri(uri: &str) -> Result<()> {
    require!(!uri.is_empty(), RegistryError::UriEmpty);
    require!(uri.len() <= MAX_URI_LEN, RegistryError::UriTooLong);
    Ok(())
}

pub fn validate_hash(hash: &[u8; 32]) -> Result<()> {
    require!(*hash != [0u8; 32], RegistryError::MissingHash);
    Ok(())
}


#[derive(Accounts)]
pub struct AcceptAuthorityTransfer<'info> {
    pub pending_authority: Signer<'info>,
    #[account(mut)]
    pub project: Account<'info, Project>,
}

pub fn accept_authority_transfer(ctx: Context<AcceptAuthorityTransfer>) -> Result<()> {
    let project = &mut ctx.accounts.project;
    let signer = ctx.accounts.pending_authority.key();
    require!(
        project.pending_authority == Some(signer),
        RegistryError::NoPendingAuthority
    );
    project.authority = signer;
    project.pending_authority = None;
    Ok(())
}


#[derive(Accounts)]
pub struct UpdateProjectMetadata<'info> {
    pub authority: Signer<'info>,
    #[account(mut, has_one = authority)]
    pub project: Account<'info, Project>,
}

pub fn update_project_metadata(
    ctx: Context<UpdateProjectMetadata>,
    metadata_hash: [u8; 32],
    metadata_uri: String,
) -> Result<()> {
    validate_hash(&metadata_hash)?;
    validate_uri(&metadata_uri)?;
    let project = &mut ctx.accounts.project;
    project.metadata_hash = metadata_hash;
    project.metadata_uri = metadata_uri;
    Ok(())
}

#[derive(Accounts)]
pub struct ProposeAuthorityTransfer<'info> {
    pub authority: Signer<'info>,
    #[account(mut, has_one = authority)]
    pub project: Account<'info, Project>,
}

pub fn propose_authority_transfer(
    ctx: Context<ProposeAuthorityTransfer>,
    new_authority: Pubkey,
) -> Result<()> {
    require_keys_neq!(
        new_authority,
        Pubkey::default(),
        RegistryError::InvalidIdentifier
    );
    require_keys_neq!(
        new_authority,
        ctx.accounts.project.authority,
        RegistryError::InvalidIdentifier
    );
    ctx.accounts.project.pending_authority = Some(new_authority);
    Ok(())
}

#[derive(Accounts)]
pub struct UpdateProjectStatus<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(
        seeds = [REGISTRY_SEED],
        bump = registry.bump,
        has_one = admin @ RegistryError::UnauthorizedAdmin
    )]
    pub registry: Account<'info, Registry>,
    #[account(mut)]
    pub project: Account<'info, Project>,
}

pub fn update_project_status(
    ctx: Context<UpdateProjectStatus>,
    lifecycle_status: LifecycleStatus,
) -> Result<()> {
    require!(
        ctx.accounts.registry.schema_version == SCHEMA_VERSION,
        RegistryError::SchemaMismatch
    );
    ctx.accounts.project.lifecycle_status = lifecycle_status;
    Ok(())
}
