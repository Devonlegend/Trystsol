use anchor_lang::prelude::*;

use crate::{
    constants::*,
    error::RegistryError,
    state::{Decision, Milestone, MilestoneStatus, Project, Registry, Reviewer, Verification},
};

#[derive(Accounts)]
#[instruction(milestone_id: [u8; 16])]
pub struct SubmitVerdict<'info> {
    #[account(mut)]
    pub reviewer_wallet: Signer<'info>,
    #[account(seeds = [REGISTRY_SEED], bump = registry.bump)]
    pub registry: Account<'info, Registry>,
    #[account(
        seeds = [REVIEWER_SEED, registry.key().as_ref(), reviewer_wallet.key().as_ref()],
        bump = reviewer.bump
    )]
    pub reviewer: Account<'info, Reviewer>,
    pub project: Account<'info, Project>,
    #[account(
        mut,
        seeds = [MILESTONE_SEED, project.key().as_ref(), milestone_id.as_ref()],
        bump = milestone.bump
    )]
    pub milestone: Account<'info, Milestone>,
    #[account(
        init,
        payer = reviewer_wallet,
        space = 8 + Verification::INIT_SPACE,
        seeds = [
            VERIFICATION_SEED,
            milestone.key().as_ref(),
            milestone.round.to_le_bytes().as_ref(),
            reviewer_wallet.key().as_ref()
        ],
        bump
    )]
    pub verification: Account<'info, Verification>,
    pub system_program: Program<'info, System>,
}

pub fn verify_milestone(ctx: Context<SubmitVerdict>, milestone_id: [u8; 16]) -> Result<()> {
    submit_verdict(ctx, milestone_id, Decision::Verify)
}

pub fn reject_milestone(ctx: Context<SubmitVerdict>, milestone_id: [u8; 16]) -> Result<()> {
    submit_verdict(ctx, milestone_id, Decision::Reject)
}

fn submit_verdict(
    ctx: Context<SubmitVerdict>,
    milestone_id: [u8; 16],
    decision: Decision,
) -> Result<()> {
    let reviewer = &ctx.accounts.reviewer;
    let project = &ctx.accounts.project;
    let milestone = &mut ctx.accounts.milestone;
    let wallet = ctx.accounts.reviewer_wallet.key();

    require!(reviewer.active, RegistryError::ReviewerInactive);
    require_keys_eq!(reviewer.wallet, wallet, RegistryError::ReviewerMismatch);
    require_keys_eq!(milestone.project, project.key(), RegistryError::InvalidIdentifier);
    require!(milestone.milestone_id == milestone_id, RegistryError::InvalidIdentifier);
    require_keys_neq!(project.authority, wallet, RegistryError::AuthorityCannotReview);
    require!(
        matches!(
            milestone.status,
            MilestoneStatus::Submitted | MilestoneStatus::UnderReview
        ),
        RegistryError::InvalidMilestoneStatus
    );
    require!(milestone.round >= 1, RegistryError::InvalidMilestoneStatus);
    require!(
        milestone.assigned_reviewers.contains(&wallet),
        RegistryError::ReviewerNotAssigned
    );
    require!(
        milestone.required_approvals >= 1
            && milestone.required_approvals as usize <= milestone.assigned_reviewers.len(),
        RegistryError::InvalidApprovals
    );

    match decision {
        Decision::Verify => {
            milestone.approvals = milestone
                .approvals
                .checked_add(1)
                .ok_or(RegistryError::RoundOverflow)?;
        }
        Decision::Reject => {
            milestone.rejections = milestone
                .rejections
                .checked_add(1)
                .ok_or(RegistryError::RoundOverflow)?;
        }
    }

    // With N assigned reviewers and R required approvals, approval becomes impossible
    // once rejections reach N - R + 1.
    let reviewer_count = milestone.assigned_reviewers.len() as u16;
    let required = milestone.required_approvals as u16;
    let rejection_limit = reviewer_count - required + 1;

    let now = Clock::get()?.unix_timestamp;
    if milestone.approvals as u16 >= required {
        milestone.status = MilestoneStatus::Verified;
        milestone.finalized_at = now;
    } else if milestone.rejections as u16 >= rejection_limit {
        milestone.status = MilestoneStatus::Rejected;
        milestone.finalized_at = now;
    } else {
        milestone.status = MilestoneStatus::UnderReview;
    }

    let verification = &mut ctx.accounts.verification;
    verification.milestone = milestone.key();
    verification.round = milestone.round;
    verification.reviewer = wallet;
    verification.decision = decision;
    verification.evidence_hash = milestone.evidence_hash;
    verification.criteria_hash = milestone.criteria_hash;
    verification.timestamp = now;
    verification.bump = ctx.bumps.verification;
    Ok(())
}
