use anchor_lang::{
    prelude::Pubkey,
    solana_program::{instruction::Instruction, system_program},
    AccountDeserialize, InstructionData, ToAccountMetas,
};
use litesvm::LiteSVM;
use solana_clock::Clock;
use solana_keypair::Keypair;
use solana_message::{Message, VersionedMessage};
use solana_signer::Signer;
use solana_transaction::versioned::VersionedTransaction;

use project_registry::{
    constants::{
        CRITERIA_SEED, MILESTONE_SEED, PROJECT_SEED, REGISTRY_SEED, REVIEWER_SEED,
        VERIFICATION_SEED,
    },
    state::{
        CriteriaTemplate, Decision, LifecycleStatus, Milestone, MilestoneStatus, Project,
        Registry, Reviewer, Verification,
    },
};

const PROJECT_ID: [u8; 16] = [1u8; 16];
const MILESTONE_ID: [u8; 16] = [2u8; 16];
const OTHER_MILESTONE_ID: [u8; 16] = [3u8; 16];
const CRITERIA_ID: [u8; 16] = [4u8; 16];
const CRITERIA_HASH: [u8; 32] = [6u8; 32];

struct Env {
    svm: LiteSVM,
    admin: Keypair,
    founder: Keypair,
    reviewer: Keypair,
    reviewer_two: Keypair,
    reviewer_three: Keypair,
    outsider: Keypair,
}

fn setup() -> Env {
    let program_id = project_registry::id();
    let mut svm = LiteSVM::new();
    let bytes = include_bytes!(concat!(
        env!("CARGO_TARGET_TMPDIR"),
        "/../deploy/project_registry.so"
    ));
    svm.add_program(program_id, bytes).unwrap();
    svm.set_sysvar(&Clock {
        unix_timestamp: 1_700_000_000,
        ..Clock::default()
    });

    let admin = Keypair::new();
    let founder = Keypair::new();
    let reviewer = Keypair::new();
    let reviewer_two = Keypair::new();
    let reviewer_three = Keypair::new();
    let outsider = Keypair::new();

    for keypair in [
        &admin,
        &founder,
        &reviewer,
        &reviewer_two,
        &reviewer_three,
        &outsider,
    ] {
        svm.airdrop(&keypair.pubkey(), 10_000_000_000).unwrap();
    }

    Env {
        svm,
        admin,
        founder,
        reviewer,
        reviewer_two,
        reviewer_three,
        outsider,
    }
}

fn copy(keypair: &Keypair) -> Keypair {
    let bytes = keypair.to_bytes();
    let secret: [u8; 32] = bytes[..32].try_into().expect("secret key");
    Keypair::new_from_array(secret)
}

fn send(
    svm: &mut LiteSVM,
    instructions: &[Instruction],
    payer: &Keypair,
    signers: &[&Keypair],
) -> Result<(), String> {
    svm.expire_blockhash();
    let blockhash = svm.latest_blockhash();
    let message = Message::new_with_blockhash(instructions, Some(&payer.pubkey()), &blockhash);
    let transaction = VersionedTransaction::try_new(VersionedMessage::Legacy(message), signers)
        .map_err(|error| format!("{error:?}"))?;
    svm.send_transaction(transaction)
        .map(|_| ())
        .map_err(|error| format!("{error:?}"))
}

fn registry_pda() -> Pubkey {
    Pubkey::find_program_address(&[REGISTRY_SEED], &project_registry::id()).0
}

fn reviewer_pda(wallet: &Pubkey) -> Pubkey {
    Pubkey::find_program_address(
        &[REVIEWER_SEED, registry_pda().as_ref(), wallet.as_ref()],
        &project_registry::id(),
    )
    .0
}

fn project_pda(project_id: &[u8; 16]) -> Pubkey {
    Pubkey::find_program_address(
        &[PROJECT_SEED, project_id.as_ref()],
        &project_registry::id(),
    )
    .0
}

fn milestone_pda(project: &Pubkey, milestone_id: &[u8; 16]) -> Pubkey {
    Pubkey::find_program_address(
        &[MILESTONE_SEED, project.as_ref(), milestone_id.as_ref()],
        &project_registry::id(),
    )
    .0
}

fn criteria_pda(template_id: &[u8; 16]) -> Pubkey {
    Pubkey::find_program_address(
        &[CRITERIA_SEED, template_id.as_ref()],
        &project_registry::id(),
    )
    .0
}

fn verification_pda(milestone: &Pubkey, round: u16, reviewer: &Pubkey) -> Pubkey {
    Pubkey::find_program_address(
        &[
            VERIFICATION_SEED,
            milestone.as_ref(),
            round.to_le_bytes().as_ref(),
            reviewer.as_ref(),
        ],
        &project_registry::id(),
    )
    .0
}

fn initialize_registry(env: &mut Env) -> Result<(), String> {
    let admin = copy(&env.admin);
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::InitializeRegistry {}.data(),
        project_registry::accounts::InitializeRegistry {
            admin: admin.pubkey(),
            registry: registry_pda(),
            system_program: system_program::ID,
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], &admin, &[&admin])
}

fn add_reviewer(env: &mut Env, signer: &Keypair, wallet: Pubkey) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::AddReviewer { wallet }.data(),
        project_registry::accounts::AddReviewer {
            admin: signer.pubkey(),
            registry: registry_pda(),
            reviewer: reviewer_pda(&wallet),
            system_program: system_program::ID,
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn deactivate_reviewer(env: &mut Env, signer: &Keypair, wallet: Pubkey) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::DeactivateReviewer { wallet }.data(),
        project_registry::accounts::DeactivateReviewer {
            admin: signer.pubkey(),
            registry: registry_pda(),
            reviewer: reviewer_pda(&wallet),
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn publish_criteria(env: &mut Env, signer: &Keypair) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::PublishCriteriaTemplate {
            template_id: CRITERIA_ID,
            version: 1,
            criteria_hash: CRITERIA_HASH,
            criteria_uri: "https://example.test/criteria/v1".to_string(),
        }
        .data(),
        project_registry::accounts::PublishCriteriaTemplate {
            admin: signer.pubkey(),
            registry: registry_pda(),
            criteria_template: criteria_pda(&CRITERIA_ID),
            system_program: system_program::ID,
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn register_project(env: &mut Env, signer: &Keypair, founder: Pubkey) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::RegisterProject {
            project_id: PROJECT_ID,
            metadata_hash: [7u8; 32],
            metadata_uri: "https://example.test/project/1".to_string(),
            founder,
        }
        .data(),
        project_registry::accounts::RegisterProject {
            admin: signer.pubkey(),
            registry: registry_pda(),
            project: project_pda(&PROJECT_ID),
            system_program: system_program::ID,
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn accept_authority(env: &mut Env, signer: &Keypair) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::AcceptAuthorityTransfer {}.data(),
        project_registry::accounts::AcceptAuthorityTransfer {
            pending_authority: signer.pubkey(),
            project: project_pda(&PROJECT_ID),
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn create_milestone(
    env: &mut Env,
    signer: &Keypair,
    milestone_id: &[u8; 16],
    criteria_id: &[u8; 16],
) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::CreateMilestone {
            milestone_id: *milestone_id,
            criteria_template_id: *criteria_id,
        }
        .data(),
        project_registry::accounts::CreateMilestone {
            authority: signer.pubkey(),
            project: project_pda(&PROJECT_ID),
            milestone: milestone_pda(&project_pda(&PROJECT_ID), milestone_id),
            criteria_template: criteria_pda(criteria_id),
            system_program: system_program::ID,
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn assign_reviewers(
    env: &mut Env,
    signer: &Keypair,
    milestone_id: &[u8; 16],
    reviewers: &[Pubkey],
    required_approvals: u8,
) -> Result<(), String> {
    let mut metas = project_registry::accounts::AssignReviewers {
        admin: signer.pubkey(),
        registry: registry_pda(),
        project: project_pda(&PROJECT_ID),
        milestone: milestone_pda(&project_pda(&PROJECT_ID), milestone_id),
    }
    .to_account_metas(None);
    for reviewer in reviewers {
        metas.push(
            anchor_lang::solana_program::instruction::AccountMeta::new_readonly(
                reviewer_pda(reviewer),
                false,
            ),
        );
    }

    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::AssignReviewers {
            milestone_id: *milestone_id,
            reviewers: reviewers.to_vec(),
            required_approvals,
        }
        .data(),
        metas,
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn submit_milestone(
    env: &mut Env,
    signer: &Keypair,
    milestone_id: &[u8; 16],
) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::SubmitMilestone {
            milestone_id: *milestone_id,
            evidence_hash: [9u8; 32],
            evidence_uri: "https://example.test/evidence/1".to_string(),
        }
        .data(),
        project_registry::accounts::SubmitMilestone {
            authority: signer.pubkey(),
            project: project_pda(&PROJECT_ID),
            milestone: milestone_pda(&project_pda(&PROJECT_ID), milestone_id),
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn expire_round(env: &mut Env, signer: &Keypair, milestone_id: &[u8; 16]) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::ExpireRound {
            milestone_id: *milestone_id,
        }
        .data(),
        project_registry::accounts::ExpireRound {
            admin: signer.pubkey(),
            registry: registry_pda(),
            project: project_pda(&PROJECT_ID),
            milestone: milestone_pda(&project_pda(&PROJECT_ID), milestone_id),
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn submit_verdict(
    env: &mut Env,
    reviewer: &Keypair,
    milestone_id: &[u8; 16],
    verify: bool,
) -> Result<(), String> {
    let project = project_pda(&PROJECT_ID);
    let milestone = milestone_pda(&project, milestone_id);
    let round = read_milestone(env, milestone_id).round;
    let accounts = project_registry::accounts::SubmitVerdict {
        reviewer_wallet: reviewer.pubkey(),
        registry: registry_pda(),
        reviewer: reviewer_pda(&reviewer.pubkey()),
        project,
        milestone,
        verification: verification_pda(&milestone, round, &reviewer.pubkey()),
        system_program: system_program::ID,
    }
    .to_account_metas(None);

    let data = if verify {
        project_registry::instruction::VerifyMilestone {
            milestone_id: *milestone_id,
        }
        .data()
    } else {
        project_registry::instruction::RejectMilestone {
            milestone_id: *milestone_id,
        }
        .data()
    };

    let instruction = Instruction::new_with_bytes(project_registry::id(), &data, accounts);
    send(&mut env.svm, &[instruction], reviewer, &[reviewer])
}

fn read_milestone(env: &Env, milestone_id: &[u8; 16]) -> Milestone {
    let address = milestone_pda(&project_pda(&PROJECT_ID), milestone_id);
    let account = env.svm.get_account(&address).expect("milestone account");
    Milestone::try_deserialize(&mut account.data.as_slice()).expect("milestone state")
}

fn prepare(
    env: &mut Env,
    reviewer_wallets: &[Pubkey],
    required_approvals: u8,
) -> Result<(), String> {
    let admin = copy(&env.admin);
    let founder = copy(&env.founder);
    initialize_registry(env)?;
    for wallet in reviewer_wallets {
        add_reviewer(env, &admin, *wallet)?;
    }
    publish_criteria(env, &admin)?;
    register_project(env, &admin, founder.pubkey())?;
    accept_authority(env, &founder)?;
    create_milestone(env, &founder, &MILESTONE_ID, &CRITERIA_ID)?;
    assign_reviewers(env, &admin, &MILESTONE_ID, reviewer_wallets, required_approvals)
}


fn propose_registry_admin(
    env: &mut Env,
    signer: &Keypair,
    new_admin: Pubkey,
) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::ProposeRegistryAdmin { new_admin }.data(),
        project_registry::accounts::ProposeRegistryAdmin {
            admin: signer.pubkey(),
            registry: registry_pda(),
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn accept_registry_admin(env: &mut Env, signer: &Keypair) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::AcceptRegistryAdmin {}.data(),
        project_registry::accounts::AcceptRegistryAdmin {
            pending_admin: signer.pubkey(),
            registry: registry_pda(),
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn update_project_metadata(
    env: &mut Env,
    signer: &Keypair,
    metadata_hash: [u8; 32],
    metadata_uri: String,
) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::UpdateProjectMetadata {
            metadata_hash,
            metadata_uri,
        }
        .data(),
        project_registry::accounts::UpdateProjectMetadata {
            authority: signer.pubkey(),
            project: project_pda(&PROJECT_ID),
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn propose_authority_transfer(
    env: &mut Env,
    signer: &Keypair,
    new_authority: Pubkey,
) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::ProposeAuthorityTransfer { new_authority }.data(),
        project_registry::accounts::ProposeAuthorityTransfer {
            authority: signer.pubkey(),
            project: project_pda(&PROJECT_ID),
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn update_project_status(
    env: &mut Env,
    signer: &Keypair,
    status: LifecycleStatus,
) -> Result<(), String> {
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::UpdateProjectStatus {
            lifecycle_status: status,
        }
        .data(),
        project_registry::accounts::UpdateProjectStatus {
            admin: signer.pubkey(),
            registry: registry_pda(),
            project: project_pda(&PROJECT_ID),
        }
        .to_account_metas(None),
    );
    send(&mut env.svm, &[instruction], signer, &[signer])
}

fn read_registry(env: &Env) -> Registry {
    let account = env.svm.get_account(&registry_pda()).expect("registry account");
    Registry::try_deserialize(&mut account.data.as_slice()).expect("registry state")
}

fn read_project(env: &Env) -> Project {
    let account = env.svm.get_account(&project_pda(&PROJECT_ID)).expect("project account");
    Project::try_deserialize(&mut account.data.as_slice()).expect("project state")
}

#[test]
fn happy_path_uses_admin_criteria_and_records_history() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let admin = copy(&_admin);
    let founder = copy(&_founder);
    let reviewer = copy(&_one);
    let reviewer_wallet = reviewer.pubkey();

    prepare(&mut env, &[reviewer_wallet], 1).unwrap();

    let milestone = read_milestone(&env, &MILESTONE_ID);
    assert_eq!(milestone.status, MilestoneStatus::Pending);
    assert_eq!(milestone.criteria_hash, CRITERIA_HASH);
    assert_eq!(milestone.criteria_version, 1);
    assert_eq!(milestone.criteria_template_id, CRITERIA_ID);

    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();
    let milestone = read_milestone(&env, &MILESTONE_ID);
    assert_eq!(milestone.status, MilestoneStatus::Submitted);
    assert_eq!(milestone.round, 1);
    assert_eq!(milestone.evidence_hash, [9u8; 32]);
    assert_eq!(milestone.criteria_hash, CRITERIA_HASH);

    submit_verdict(&mut env, &reviewer, &MILESTONE_ID, true).unwrap();
    let milestone = read_milestone(&env, &MILESTONE_ID);
    assert_eq!(milestone.status, MilestoneStatus::Verified);
    assert_eq!(milestone.approvals, 1);
    assert!(milestone.finalized_at > 0);

    let registry_account = env.svm.get_account(&registry_pda()).unwrap();
    let registry = Registry::try_deserialize(&mut registry_account.data.as_slice()).unwrap();
    assert_eq!(registry.admin, admin.pubkey());
    assert_eq!(registry.reviewer_count, 1);

    let project_account = env.svm.get_account(&project_pda(&PROJECT_ID)).unwrap();
    let project = Project::try_deserialize(&mut project_account.data.as_slice()).unwrap();
    assert_eq!(project.authority, founder.pubkey());
    assert_eq!(project.pending_authority, None);

    let template_account = env.svm.get_account(&criteria_pda(&CRITERIA_ID)).unwrap();
    let template =
        CriteriaTemplate::try_deserialize(&mut template_account.data.as_slice()).unwrap();
    assert_eq!(template.criteria_hash, CRITERIA_HASH);
    assert!(template.active);

    let milestone_pubkey = milestone_pda(&project_pda(&PROJECT_ID), &MILESTONE_ID);
    let verification_address = verification_pda(&milestone_pubkey, 1, &reviewer_wallet);
    let verification_account = env.svm.get_account(&verification_address).unwrap();
    let verification =
        Verification::try_deserialize(&mut verification_account.data.as_slice()).unwrap();
    assert_eq!(verification.decision, Decision::Verify);
    assert_eq!(verification.criteria_hash, CRITERIA_HASH);
}

#[test]
fn founder_must_accept_authority_before_milestones() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let admin = copy(&_admin);
    let founder = copy(&_founder);
    let outsider = copy(&_outsider);

    initialize_registry(&mut env).unwrap();
    publish_criteria(&mut env, &admin).unwrap();
    register_project(&mut env, &admin, founder.pubkey()).unwrap();

    // Admin is interim authority; the founder has not accepted.
    let before = create_milestone(&mut env, &founder, &MILESTONE_ID, &CRITERIA_ID);
    assert!(before.is_err());
    let wrong_signer = accept_authority(&mut env, &outsider);
    assert!(wrong_signer.is_err());
    accept_authority(&mut env, &founder).unwrap();
    create_milestone(&mut env, &founder, &MILESTONE_ID, &CRITERIA_ID).unwrap();
}

#[test]
fn criteria_cannot_be_chosen_or_changed_by_the_founder() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let admin = copy(&_admin);
    let founder = copy(&_founder);

    initialize_registry(&mut env).unwrap();
    publish_criteria(&mut env, &admin).unwrap();
    register_project(&mut env, &admin, founder.pubkey()).unwrap();
    accept_authority(&mut env, &founder).unwrap();

    // A different template id has no account, so the constraint fails.
    let wrong_id = [99u8; 16];
    let wrong = create_milestone(&mut env, &founder, &MILESTONE_ID, &wrong_id);
    assert!(wrong.is_err());

    create_milestone(&mut env, &founder, &MILESTONE_ID, &CRITERIA_ID).unwrap();
    let milestone = read_milestone(&env, &MILESTONE_ID);
    assert_eq!(milestone.criteria_hash, CRITERIA_HASH);
    assert_eq!(milestone.criteria_version, 1);

    add_reviewer(&mut env, &_admin, _one.pubkey()).unwrap();
    assign_reviewers(&mut env, &_admin, &MILESTONE_ID, &[_one.pubkey()], 1).unwrap();

    // Submission has no criteria arguments and leaves them untouched.
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();
    let after = read_milestone(&env, &MILESTONE_ID);
    assert_eq!(after.criteria_hash, CRITERIA_HASH);
    assert_eq!(after.criteria_version, 1);
    assert_eq!(after.criteria_template_id, CRITERIA_ID);
}

#[test]
fn required_approvals_greater_than_reviewer_count_is_rejected() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let admin = copy(&_admin);
    let founder = copy(&_founder);

    initialize_registry(&mut env).unwrap();
    add_reviewer(&mut env, &admin, _one.pubkey()).unwrap();
    publish_criteria(&mut env, &admin).unwrap();
    register_project(&mut env, &admin, founder.pubkey()).unwrap();
    accept_authority(&mut env, &founder).unwrap();
    create_milestone(&mut env, &founder, &MILESTONE_ID, &CRITERIA_ID).unwrap();

    let result = assign_reviewers(
        &mut env,
        &admin,
        &MILESTONE_ID,
        &[_one.pubkey()],
        2,
    );
    assert!(result.is_err());
}

#[test]
fn deactivated_reviewer_deadlock_is_expired_and_recovered() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let admin = copy(&_admin);
    let founder = copy(&_founder);
    let one = copy(&_one);
    let two = copy(&_two);
    let three = copy(&_three);

    prepare(&mut env, &[one.pubkey(), two.pubkey()], 2).unwrap();
    add_reviewer(&mut env, &admin, three.pubkey()).unwrap();
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();

    deactivate_reviewer(&mut env, &admin, one.pubkey()).unwrap();
    let inactive_verdict = submit_verdict(&mut env, &one, &MILESTONE_ID, true);
    assert!(inactive_verdict.is_err());

    submit_verdict(&mut env, &two, &MILESTONE_ID, true).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::UnderReview
    );

    // No reassignment after a verdict in the current round.
    let reassign = assign_reviewers(
        &mut env,
        &admin,
        &MILESTONE_ID,
        &[two.pubkey(), three.pubkey()],
        2,
    );
    assert!(reassign.is_err());

    // Admin expires the stuck round; history remains.
    expire_round(&mut env, &admin, &MILESTONE_ID).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::Rejected
    );

    assign_reviewers(
        &mut env,
        &admin,
        &MILESTONE_ID,
        &[two.pubkey(), three.pubkey()],
        2,
    )
    .unwrap();
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();
    assert_eq!(read_milestone(&env, &MILESTONE_ID).round, 2);

    submit_verdict(&mut env, &two, &MILESTONE_ID, true).unwrap();
    submit_verdict(&mut env, &three, &MILESTONE_ID, true).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::Verified
    );

    // Round 1 verdict and round 2 verdicts all persist.
    let milestone_pubkey = milestone_pda(&project_pda(&PROJECT_ID), &MILESTONE_ID);
    let round_one = verification_pda(&milestone_pubkey, 1, &two.pubkey());
    let round_two_one = verification_pda(&milestone_pubkey, 2, &two.pubkey());
    let round_two_two = verification_pda(&milestone_pubkey, 2, &three.pubkey());
    for address in [round_one, round_two_one, round_two_two] {
        assert!(env.svm.get_account(&address).is_some());
    }
}

#[test]
fn project_authority_cannot_review_its_own_milestone() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let founder = copy(&_founder);
    prepare(&mut env, &[founder.pubkey()], 1).unwrap();
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();

    let result = submit_verdict(&mut env, &founder, &MILESTONE_ID, true);
    assert!(result.is_err());
}

#[test]
fn unassigned_reviewer_is_rejected() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let admin = copy(&_admin);
    let founder = copy(&_founder);
    let assigned = _one.pubkey();
    let unassigned = _two.pubkey();
    prepare(&mut env, &[assigned], 1).unwrap();
    add_reviewer(&mut env, &admin, unassigned).unwrap();
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();

    let result = submit_verdict(&mut env, &_two, &MILESTONE_ID, true);
    assert!(result.is_err());
}

#[test]
fn reviewer_cannot_submit_two_verdicts_in_one_round() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let founder = copy(&_founder);
    prepare(&mut env, &[_one.pubkey(), _two.pubkey()], 2).unwrap();
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();

    submit_verdict(&mut env, &_one, &MILESTONE_ID, true).unwrap();
    let second = submit_verdict(&mut env, &_one, &MILESTONE_ID, true);
    assert!(second.is_err());
}

#[test]
fn cannot_verify_before_submission() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    prepare(&mut env, &[_one.pubkey()], 1).unwrap();

    let result = submit_verdict(&mut env, &_one, &MILESTONE_ID, true);
    assert!(result.is_err());
}

#[test]
fn only_admin_can_register_publish_or_manage_reviewers() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let outsider = copy(&_outsider);
    initialize_registry(&mut env).unwrap();

    let add = add_reviewer(&mut env, &outsider, _one.pubkey());
    assert!(add.is_err());
    let publish = publish_criteria(&mut env, &outsider);
    assert!(publish.is_err());
    let register = register_project(&mut env, &outsider, _founder.pubkey());
    assert!(register.is_err());
    let deactivate = deactivate_reviewer(&mut env, &outsider, _one.pubkey());
    assert!(deactivate.is_err());
}

#[test]
fn rejection_then_resubmission_keeps_both_rounds() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let founder = copy(&_founder);
    let reviewer_wallet = _one.pubkey();
    prepare(&mut env, &[reviewer_wallet], 1).unwrap();

    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();
    submit_verdict(&mut env, &_one, &MILESTONE_ID, false).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::Rejected
    );

    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();
    assert_eq!(read_milestone(&env, &MILESTONE_ID).round, 2);
    submit_verdict(&mut env, &_one, &MILESTONE_ID, true).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::Verified
    );

    let milestone_pubkey = milestone_pda(&project_pda(&PROJECT_ID), &MILESTONE_ID);
    for round in 1..=2u16 {
        let address = verification_pda(&milestone_pubkey, round, &reviewer_wallet);
        assert!(env.svm.get_account(&address).is_some());
    }
}

#[test]
fn rejection_threshold_finalises_only_when_approval_is_impossible() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let founder = copy(&_founder);
    let one = _one.pubkey();
    let two = _two.pubkey();
    let three = _three.pubkey();
    prepare(&mut env, &[one, two, three], 2).unwrap();
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();

    submit_verdict(&mut env, &_one, &MILESTONE_ID, true).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::UnderReview
    );

    submit_verdict(&mut env, &_two, &MILESTONE_ID, false).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::UnderReview
    );

    submit_verdict(&mut env, &_three, &MILESTONE_ID, false).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::Rejected
    );
}

#[test]
fn required_approvals_are_enforced() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let founder = copy(&_founder);
    prepare(&mut env, &[_one.pubkey(), _two.pubkey()], 2).unwrap();
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();

    submit_verdict(&mut env, &_one, &MILESTONE_ID, true).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::UnderReview
    );
    submit_verdict(&mut env, &_two, &MILESTONE_ID, true).unwrap();
    assert_eq!(
        read_milestone(&env, &MILESTONE_ID).status,
        MilestoneStatus::Verified
    );
}

#[test]
fn wrong_milestone_identifier_is_rejected() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let founder = copy(&_founder);
    prepare(&mut env, &[_one.pubkey()], 1).unwrap();
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();

    let project = project_pda(&PROJECT_ID);
    let milestone = milestone_pda(&project, &MILESTONE_ID);
    let data = project_registry::instruction::VerifyMilestone {
        milestone_id: OTHER_MILESTONE_ID,
    }
    .data();
    let accounts = project_registry::accounts::SubmitVerdict {
        reviewer_wallet: _one.pubkey(),
        registry: registry_pda(),
        reviewer: reviewer_pda(&_one.pubkey()),
        project,
        milestone,
        verification: verification_pda(&milestone, 1, &_one.pubkey()),
        system_program: system_program::ID,
    }
    .to_account_metas(None);
    let instruction = Instruction::new_with_bytes(project_registry::id(), &data, accounts);

    let result = send(
        &mut env.svm,
        &[instruction],
        &_one,
        &[&_one],
    );
    assert!(result.is_err());
}

#[test]
fn fake_milestone_account_is_rejected() {
    let mut env = setup();
    let _admin = copy(&env.admin);
    let _founder = copy(&env.founder);
    let _one = copy(&env.reviewer);
    let _two = copy(&env.reviewer_two);
    let _three = copy(&env.reviewer_three);
    let _outsider = copy(&env.outsider);
    let founder = copy(&_founder);
    prepare(&mut env, &[_one.pubkey()], 1).unwrap();
    submit_milestone(&mut env, &founder, &MILESTONE_ID).unwrap();

    let fake = Pubkey::new_unique();
    let data = project_registry::instruction::VerifyMilestone {
        milestone_id: MILESTONE_ID,
    }
    .data();
    let accounts = project_registry::accounts::SubmitVerdict {
        reviewer_wallet: _one.pubkey(),
        registry: registry_pda(),
        reviewer: reviewer_pda(&_one.pubkey()),
        project: project_pda(&PROJECT_ID),
        milestone: fake,
        verification: verification_pda(&fake, 1, &_one.pubkey()),
        system_program: system_program::ID,
    }
    .to_account_metas(None);
    let instruction = Instruction::new_with_bytes(project_registry::id(), &data, accounts);

    let result = send(
        &mut env.svm,
        &[instruction],
        &_one,
        &[&_one],
    );
    assert!(result.is_err());
}


#[test]
fn registry_admin_transfer_is_two_step() {
    let mut env = setup();
    let admin = copy(&env.admin);
    let outsider = copy(&env.outsider);
    let reviewer = copy(&env.reviewer);
    initialize_registry(&mut env).unwrap();

    propose_registry_admin(&mut env, &admin, outsider.pubkey()).unwrap();
    let registry = read_registry(&env);
    assert_eq!(registry.admin, admin.pubkey());
    assert_eq!(registry.pending_admin, Some(outsider.pubkey()));

    // Only the pending admin can accept.
    assert!(accept_registry_admin(&mut env, &reviewer).is_err());
    accept_registry_admin(&mut env, &outsider).unwrap();
    let registry = read_registry(&env);
    assert_eq!(registry.admin, outsider.pubkey());
    assert_eq!(registry.pending_admin, None);

    // The old admin loses authority; the new admin can act.
    assert!(add_reviewer(&mut env, &admin, reviewer.pubkey()).is_err());
    add_reviewer(&mut env, &outsider, reviewer.pubkey()).unwrap();
}

#[test]
fn project_metadata_and_authority_transfer_are_enforced() {
    let mut env = setup();
    let admin = copy(&env.admin);
    let founder = copy(&env.founder);
    let outsider = copy(&env.outsider);
    let reviewer = copy(&env.reviewer);
    prepare(&mut env, &[reviewer.pubkey()], 1).unwrap();

    update_project_metadata(
        &mut env,
        &founder,
        [8u8; 32],
        "https://example.test/project/updated".to_string(),
    )
    .unwrap();
    let project = read_project(&env);
    assert_eq!(project.metadata_hash, [8u8; 32]);

    assert!(update_project_metadata(
        &mut env,
        &outsider,
        [9u8; 32],
        "https://example.test/evil".to_string(),
    )
    .is_err());

    propose_authority_transfer(&mut env, &founder, outsider.pubkey()).unwrap();
    assert!(accept_authority(&mut env, &admin).is_err());
    assert!(propose_authority_transfer(&mut env, &outsider, founder.pubkey()).is_err());
    accept_authority(&mut env, &outsider).unwrap();

    let project = read_project(&env);
    assert_eq!(project.authority, outsider.pubkey());
    assert_eq!(project.pending_authority, None);

    // Old authority is locked out; new authority can update and create.
    assert!(update_project_metadata(
        &mut env,
        &founder,
        [1u8; 32],
        "https://example.test/stale".to_string(),
    )
    .is_err());
    update_project_metadata(
        &mut env,
        &outsider,
        [2u8; 32],
        "https://example.test/new".to_string(),
    )
    .unwrap();
    assert!(create_milestone(&mut env, &founder, &OTHER_MILESTONE_ID, &CRITERIA_ID).is_err());
    create_milestone(&mut env, &outsider, &OTHER_MILESTONE_ID, &CRITERIA_ID).unwrap();
}

#[test]
fn project_status_is_admin_only_and_suspension_blocks_milestones() {
    let mut env = setup();
    let admin = copy(&env.admin);
    let founder = copy(&env.founder);
    let reviewer = copy(&env.reviewer);
    prepare(&mut env, &[reviewer.pubkey()], 1).unwrap();

    assert!(update_project_status(&mut env, &founder, LifecycleStatus::Suspended).is_err());
    update_project_status(&mut env, &admin, LifecycleStatus::Suspended).unwrap();
    assert_eq!(read_project(&env).lifecycle_status, LifecycleStatus::Suspended);
    assert!(create_milestone(&mut env, &founder, &OTHER_MILESTONE_ID, &CRITERIA_ID).is_err());

    update_project_status(&mut env, &admin, LifecycleStatus::Active).unwrap();
    create_milestone(&mut env, &founder, &OTHER_MILESTONE_ID, &CRITERIA_ID).unwrap();
}

#[test]
fn wrong_owner_account_is_rejected() {
    let mut env = setup();
    let admin = copy(&env.admin);
    let outsider = copy(&env.outsider);
    initialize_registry(&mut env).unwrap();

    // A system-owned account cannot be deserialized as a Project.
    let instruction = Instruction::new_with_bytes(
        project_registry::id(),
        &project_registry::instruction::AcceptAuthorityTransfer {}.data(),
        project_registry::accounts::AcceptAuthorityTransfer {
            pending_authority: outsider.pubkey(),
            project: admin.pubkey(),
        }
        .to_account_metas(None),
    );
    let result = send(&mut env.svm, &[instruction], &outsider, &[&outsider]);
    assert!(result.is_err());
}
