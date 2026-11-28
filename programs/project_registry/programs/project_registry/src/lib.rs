pub mod constants;
pub mod error;
pub mod instructions;
pub mod state;

use anchor_lang::prelude::*;

pub use constants::*;
pub use state::*;

use instructions::*;

declare_id!("CThoKseeGQf6wN4jVADhLm549Nw89rsNL8p684iTK8BB");

#[program]
pub mod project_registry {
    use super::*;

    pub fn initialize_registry(ctx: Context<InitializeRegistry>) -> Result<()> {
        instructions::registry::initialize_registry(ctx)
    }

    pub fn add_reviewer(ctx: Context<AddReviewer>, wallet: Pubkey) -> Result<()> {
        instructions::registry::add_reviewer(ctx, wallet)
    }

    pub fn propose_registry_admin(
        ctx: Context<ProposeRegistryAdmin>,
        new_admin: Pubkey,
    ) -> Result<()> {
        instructions::registry::propose_registry_admin(ctx, new_admin)
    }

    pub fn accept_registry_admin(ctx: Context<AcceptRegistryAdmin>) -> Result<()> {
        instructions::registry::accept_registry_admin(ctx)
    }

    pub fn deactivate_reviewer(ctx: Context<DeactivateReviewer>, wallet: Pubkey) -> Result<()> {
        instructions::registry::deactivate_reviewer(ctx, wallet)
    }

    pub fn publish_criteria_template(
        ctx: Context<PublishCriteriaTemplate>,
        template_id: [u8; 16],
        version: u16,
        criteria_hash: [u8; 32],
        criteria_uri: String,
    ) -> Result<()> {
        instructions::registry::publish_criteria_template(
            ctx,
            template_id,
            version,
            criteria_hash,
            criteria_uri,
        )
    }

    pub fn register_project(
        ctx: Context<RegisterProject>,
        project_id: [u8; 16],
        metadata_hash: [u8; 32],
        metadata_uri: String,
        founder: Pubkey,
    ) -> Result<()> {
        instructions::project::register_project(
            ctx,
            project_id,
            metadata_hash,
            metadata_uri,
            founder,
        )
    }

    pub fn accept_authority_transfer(ctx: Context<AcceptAuthorityTransfer>) -> Result<()> {
        instructions::project::accept_authority_transfer(ctx)
    }

    pub fn propose_authority_transfer(
        ctx: Context<ProposeAuthorityTransfer>,
        new_authority: Pubkey,
    ) -> Result<()> {
        instructions::project::propose_authority_transfer(ctx, new_authority)
    }

    pub fn update_project_metadata(
        ctx: Context<UpdateProjectMetadata>,
        metadata_hash: [u8; 32],
        metadata_uri: String,
    ) -> Result<()> {
        instructions::project::update_project_metadata(ctx, metadata_hash, metadata_uri)
    }

    pub fn update_project_status(
        ctx: Context<UpdateProjectStatus>,
        lifecycle_status: LifecycleStatus,
    ) -> Result<()> {
        instructions::project::update_project_status(ctx, lifecycle_status)
    }

    pub fn create_milestone(
        ctx: Context<CreateMilestone>,
        milestone_id: [u8; 16],
        criteria_template_id: [u8; 16],
    ) -> Result<()> {
        instructions::milestone::create_milestone(ctx, milestone_id, criteria_template_id)
    }

    pub fn assign_reviewers(
        ctx: Context<AssignReviewers>,
        milestone_id: [u8; 16],
        reviewers: Vec<Pubkey>,
        required_approvals: u8,
    ) -> Result<()> {
        instructions::milestone::assign_reviewers(ctx, milestone_id, reviewers, required_approvals)
    }

    pub fn submit_milestone(
        ctx: Context<SubmitMilestone>,
        milestone_id: [u8; 16],
        evidence_hash: [u8; 32],
        evidence_uri: String,
    ) -> Result<()> {
        instructions::milestone::submit_milestone(ctx, milestone_id, evidence_hash, evidence_uri)
    }

    pub fn expire_round(ctx: Context<ExpireRound>, milestone_id: [u8; 16]) -> Result<()> {
        instructions::milestone::expire_round(ctx, milestone_id)
    }

    pub fn verify_milestone(ctx: Context<SubmitVerdict>, milestone_id: [u8; 16]) -> Result<()> {
        instructions::review::verify_milestone(ctx, milestone_id)
    }

    pub fn reject_milestone(ctx: Context<SubmitVerdict>, milestone_id: [u8; 16]) -> Result<()> {
        instructions::review::reject_milestone(ctx, milestone_id)
    }
}
