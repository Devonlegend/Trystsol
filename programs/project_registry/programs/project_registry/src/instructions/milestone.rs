use anchor_lang::prelude::*;

use crate::{
    constants::*,
    error::RegistryError,
    instructions::project::{validate_hash, validate_uri},
    state::{
        CriteriaTemplate, LifecycleStatus, Milestone, MilestoneStatus, Project, Registry, Reviewer,
    },
};

#[derive(Accounts)]
#[instruction(milestone_id: [u8; 16], criteria_template_id: [u8; 16])]
pub struct CreateMilestone<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(has_one = authority)]
    pub project: Account<'info, Project>,
    #[account(
        init,
        payer = authority,
        space = 8 + Milestone::INIT_SPACE,
        seeds = [MILESTONE_SEED, project.key().as_ref(), milestone_id.as_ref()],
        bump
    )]
    pub milestone: Account<'info, Milestone>,
    #[account(
        seeds = [CRITERIA_SEED, criteria_template_id.as_ref()],
        bump = criteria_template.bump
    )]
    pub criteria_template: Account<'info, CriteriaTemplate>,
    pub system_program: Program<'info, System>,
}

pub fn create_milestone(
    ctx: Context<CreateMilestone>,
    milestone_id: [u8; 16],
    criteria_template_id: [u8; 16],
) -> Result<()> {
    require!(milestone_id != [0u8; 16], RegistryError::InvalidIdentifier);
    require!(criteria_template_id != [0u8; 16], RegistryError::InvalidCriteria);
    require!(
        ctx.accounts.project.lifecycle_status == LifecycleStatus::Active,
        RegistryError::ProjectNotActive
    );
    let template = &ctx.accounts.criteria_template;
    require!(template.active, RegistryError::InvalidCriteria);
    require!(
        template.template_id == criteria_template_id,
        RegistryError::InvalidCriteria
    );

    let milestone = &mut ctx.accounts.milestone;
    milestone.project = ctx.accounts.project.key();
    milestone.milestone_id = milestone_id;
    milestone.round = 0;
    milestone.evidence_hash = [0u8; 32];
    milestone.evidence_uri = String::new();
    milestone.criteria_hash = template.criteria_hash;
    milestone.criteria_uri = template.criteria_uri.clone();
    milestone.criteria_template_id = template.template_id;
    milestone.criteria_version = template.version;
    milestone.assigned_reviewers = Vec::new();
    milestone.required_approvals = 0;
    milestone.approvals = 0;
    milestone.rejections = 0;
    milestone.status = MilestoneStatus::Pending;
    milestone.submitted_at = 0;
    milestone.finalized_at = 0;
    milestone.bump = ctx.bumps.milestone;
    Ok(())
}

#[derive(Accounts)]
#[instruction(milestone_id: [u8; 16])]
pub struct AssignReviewers<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(
        seeds = [REGISTRY_SEED],
        bump = registry.bump,
        has_one = admin @ RegistryError::UnauthorizedAdmin
    )]
    pub registry: Account<'info, Registry>,
    pub project: Account<'info, Project>,
    #[account(
        mut,
        seeds = [MILESTONE_SEED, project.key().as_ref(), milestone_id.as_ref()],
        bump = milestone.bump
    )]
    pub milestone: Account<'info, Milestone>,
}

pub fn assign_reviewers(
    ctx: Context<AssignReviewers>,
    milestone_id: [u8; 16],
    reviewers: Vec<Pubkey>,
    required_approvals: u8,
) -> Result<()> {
    let milestone = &mut ctx.accounts.milestone;
    require_keys_eq!(milestone.project, ctx.accounts.project.key(), RegistryError::InvalidIdentifier);
    require!(milestone.milestone_id == milestone_id, RegistryError::InvalidIdentifier);
    require!(
        matches!(milestone.status, MilestoneStatus::Pending | MilestoneStatus::Rejected),
        RegistryError::InvalidMilestoneStatus
    );
    require!(
        milestone.status == MilestoneStatus::Rejected
            || (milestone.approvals == 0 && milestone.rejections == 0),
        RegistryError::ReassignmentLocked
    );
    require!(
        !reviewers.is_empty() && reviewers.len() <= MAX_REVIEWERS,
        RegistryError::InvalidReviewerCount
    );
    require!(
        required_approvals >= 1 && required_approvals as usize <= reviewers.len(),
        RegistryError::InvalidApprovals
    );
    require!(
        ctx.remaining_accounts.len() == reviewers.len(),
        RegistryError::InvalidReviewerCount
    );

    let mut seen: Vec<Pubkey> = Vec::with_capacity(reviewers.len());
    for (wallet, info) in reviewers.iter().zip(ctx.remaining_accounts.iter()) {
        require!(info.owner == &crate::ID, RegistryError::ReviewerMismatch);
        let reviewer = Account::<Reviewer>::try_from(info)?;
        require_keys_eq!(reviewer.wallet, *wallet, RegistryError::ReviewerMismatch);
        require!(reviewer.active, RegistryError::ReviewerInactive);
        let expected = Pubkey::find_program_address(
            &[
                REVIEWER_SEED,
                ctx.accounts.registry.key().as_ref(),
                wallet.as_ref(),
            ],
            &crate::ID,
        )
        .0;
        require_keys_eq!(info.key(), expected, RegistryError::ReviewerMismatch);
        require!(!seen.contains(wallet), RegistryError::DuplicateReviewer);
        seen.push(*wallet);
    }

    milestone.assigned_reviewers = reviewers;
    milestone.required_approvals = required_approvals;
    Ok(())
}

#[derive(Accounts)]
#[instruction(milestone_id: [u8; 16])]
pub struct SubmitMilestone<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(has_one = authority)]
    pub project: Account<'info, Project>,
    #[account(
        mut,
        seeds = [MILESTONE_SEED, project.key().as_ref(), milestone_id.as_ref()],
        bump = milestone.bump
    )]
    pub milestone: Account<'info, Milestone>,
}

pub fn submit_milestone(
    ctx: Context<SubmitMilestone>,
    milestone_id: [u8; 16],
    evidence_hash: [u8; 32],
    evidence_uri: String,
) -> Result<()> {
    let milestone = &mut ctx.accounts.milestone;
    require_keys_eq!(milestone.project, ctx.accounts.project.key(), RegistryError::InvalidIdentifier);
    require!(milestone.milestone_id == milestone_id, RegistryError::InvalidIdentifier);
    require!(
        matches!(milestone.status, MilestoneStatus::Pending | MilestoneStatus::Rejected),
        RegistryError::InvalidMilestoneStatus
    );
    require!(
        !milestone.assigned_reviewers.is_empty() && milestone.required_approvals >= 1,
        RegistryError::ReviewersNotAssigned
    );
    require!(
        milestone.required_approvals as usize <= milestone.assigned_reviewers.len(),
        RegistryError::InvalidApprovals
    );
    validate_hash(&evidence_hash)?;
    validate_uri(&evidence_uri)?;
    // Criteria were fixed by the admin-published template at creation time.
    validate_hash(&milestone.criteria_hash)?;
    validate_uri(&milestone.criteria_uri)?;

    let round = milestone
        .round
        .checked_add(1)
        .ok_or(RegistryError::RoundOverflow)?;
    milestone.round = round;
    milestone.evidence_hash = evidence_hash;
    milestone.evidence_uri = evidence_uri;
    milestone.approvals = 0;
    milestone.rejections = 0;
    milestone.status = MilestoneStatus::Submitted;
    milestone.submitted_at = Clock::get()?.unix_timestamp;
    milestone.finalized_at = 0;
    Ok(())
}


#[derive(Accounts)]
#[instruction(milestone_id: [u8; 16])]
pub struct ExpireRound<'info> {
    #[account(mut)]
    pub admin: Signer<'info>,
    #[account(
        seeds = [REGISTRY_SEED],
        bump = registry.bump,
        has_one = admin @ RegistryError::UnauthorizedAdmin
    )]
    pub registry: Account<'info, Registry>,
    pub project: Account<'info, Project>,
    #[account(
        mut,
        seeds = [MILESTONE_SEED, project.key().as_ref(), milestone_id.as_ref()],
        bump = milestone.bump
    )]
    pub milestone: Account<'info, Milestone>,
}

pub fn expire_round(ctx: Context<ExpireRound>, milestone_id: [u8; 16]) -> Result<()> {
    let milestone = &mut ctx.accounts.milestone;
    require_keys_eq!(
        milestone.project,
        ctx.accounts.project.key(),
        RegistryError::InvalidIdentifier
    );
    require!(milestone.milestone_id == milestone_id, RegistryError::InvalidIdentifier);
    require!(
        matches!(
            milestone.status,
            MilestoneStatus::Submitted | MilestoneStatus::UnderReview
        ),
        RegistryError::InvalidRoundState
    );
    milestone.status = MilestoneStatus::Rejected;
    milestone.finalized_at = Clock::get()?.unix_timestamp;
    Ok(())
}
